import os
import random
import re
import time
from collections import defaultdict

import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai


# ============================================================
# Configuration
# ============================================================

TOTAL_QUESTIONS = 30
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
TIME_LIMIT_SECONDS = 30 * 60

# Load API key and configure the model.
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    st.error("GOOGLE_API_KEY is not configured. Add it to your environment or .env file.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")


# ============================================================
# Prompt construction
# ============================================================

MCQ_PROMPT_TEMPLATE = """
Generate exactly {num_questions} multiple-choice questions from the following topic.

Requirements:
- Generate exactly {num_questions} questions.
- Each question must have exactly 4 options.
- Use option labels a), b), c), and d).
- End every question block with "Correct: a", "Correct: b", "Correct: c", or "Correct: d".
- Do not add explanations, introductions, conclusions, markdown code fences, or extra text.
- Separate question blocks with one blank line.

Format each question exactly as follows:

1. Question text
a) Option 1
b) Option 2
c) Option 3
d) Option 4
Correct: b

Topic: {topic}

Details:
{details}
"""


def generate_prompt(topic, details, num_questions):
    """Create the final prompt sent to Gemini."""
    return MCQ_PROMPT_TEMPLATE.format(
        topic=topic,
        details=details,
        num_questions=num_questions,
    )


# ============================================================
# Gemini API + retry logic
# ============================================================

def get_gemini_response(prompt):
    """
    Call Gemini with bounded retries.

    Retry delays use exponential backoff:
        delay = initial_delay * 2^attempt

    Random jitter is added so repeated clients do not retry
    at exactly the same time.
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(prompt)

            # A response object without usable text is treated as
            # an unsuccessful generation and can be retried.
            response_text = getattr(response, "text", None)
            if not response_text or not response_text.strip():
                raise ValueError("Gemini returned an empty response.")

            return response_text

        except Exception as exc:
            last_error = exc

            # No need to sleep after the final attempt.
            if attempt == MAX_RETRIES - 1:
                break

            exponential_delay = INITIAL_BACKOFF_SECONDS * (2 ** attempt)
            jitter = random.uniform(0, 0.5)
            delay = exponential_delay + jitter

            st.warning(
                f"Gemini request failed (attempt {attempt + 1}/{MAX_RETRIES}). "
                f"Retrying in {delay:.1f} seconds..."
            )
            time.sleep(delay)

    st.error(
        f"Gemini generation failed after {MAX_RETRIES} attempts: {last_error}"
    )
    return ""


# ============================================================
# Input parsing
# ============================================================

def parse_content_by_topic(content):
    """
    Parse user input into:
        {
            "Topic 1": "detail text...",
            "Topic 2": "detail text..."
        }

    A line ending in ':' is treated as an explicit topic heading.
    If no explicit heading is present, each non-empty line is treated
    as a topic with empty details. This prevents the first line from
    accidentally becoming a topic because of parser state.
    """
    topics = {}
    current_topic = None

    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]

    for line in lines:
        if line.endswith(":"):
            topic = line[:-1].strip()
            if topic:
                current_topic = topic
                topics.setdefault(current_topic, [])
        elif current_topic is not None:
            topics[current_topic].append(line)
        else:
            # If the user supplies topic names without colon headings,
            # treat each line as a separate topic.
            topics.setdefault(line, [])

    return {
        topic: " ".join(details).strip()
        for topic, details in topics.items()
    }


# ============================================================
# Question distribution
# ============================================================

def distribute_questions(total_questions, topics):
    """
    Distribute the requested number of questions as evenly as possible.

    Example:
        30 questions across 7 topics
        -> 5, 5, 4, 4, 4, 4, 4

    The first 'remainder' topics receive one extra question.
    """
    topic_names = list(topics.keys())
    topic_count = len(topic_names)

    if topic_count == 0:
        return {}

    base = total_questions // topic_count
    remainder = total_questions % topic_count

    return {
        topic: base + (1 if index < remainder else 0)
        for index, topic in enumerate(topic_names)
    }


# ============================================================
# LLM output parsing and validation
# ============================================================

QUESTION_PATTERN = re.compile(
    r"(?ms)"
    r"^\s*(?:\d+[\.\)]\s*)?"
    r"(.+?)\s*\n"
    r"\s*a[\)\.]\s*(.+?)\s*\n"
    r"\s*b[\)\.]\s*(.+?)\s*\n"
    r"\s*c[\)\.]\s*(.+?)\s*\n"
    r"\s*d[\)\.]\s*(.+?)\s*\n"
    r"\s*Correct\s*:\s*([abcd])\s*$"
)


def parse_mcqs(mcq_text, topic=None):
    """
    Parse Gemini's text response into validated MCQ dictionaries.

    The parser accepts a few common formatting variations such as
    'a)' versus 'a.' and uppercase/lowercase Correct labels.
    Invalid question blocks are ignored rather than crashing the app.
    """
    questions = []

    if not mcq_text or not mcq_text.strip():
        return questions

    # Remove markdown code fences if Gemini adds them despite the prompt.
    cleaned_text = re.sub(r"```(?:text|markdown)?", "", mcq_text, flags=re.IGNORECASE)
    cleaned_text = cleaned_text.replace("```", "").strip()

    # Split on blank lines first, matching the requested output format.
    blocks = re.split(r"\n\s*\n", cleaned_text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        match = QUESTION_PATTERN.match(block)
        if not match:
            continue

        question_text = match.group(1).strip()
        options = [match.group(i).strip() for i in range(2, 6)]
        correct_answer = match.group(6).lower().strip()

        # Basic validation.
        if not question_text:
            continue

        if len(options) != 4 or any(not option for option in options):
            continue

        if correct_answer not in {"a", "b", "c", "d"}:
            continue

        question_data = {
            "question": question_text,
            "options": options,
            "correct": correct_answer,
        }

        if topic is not None:
            question_data["topic"] = topic

        questions.append(question_data)

    return questions


# ============================================================
# MCQ generation
# ============================================================

def generate_mcqs_per_topic(topics):
    """
    Generate the requested number of questions while retrying
    incomplete generations.

    Each generated question stores its own topic, so scoring does not
    need to search through every topic's question list later.
    """
    question_targets = distribute_questions(TOTAL_QUESTIONS, topics)

    all_questions = []
    topic_to_questions = defaultdict(list)

    for topic, details in topics.items():
        target = question_targets[topic]
        generated_questions = []

        # Each attempt asks only for the number still missing.
        for _ in range(MAX_RETRIES):
            remaining = target - len(generated_questions)

            if remaining <= 0:
                break

            prompt = generate_prompt(
                topic,
                details,
                num_questions=remaining,
            )

            response = get_gemini_response(prompt)

            new_questions = parse_mcqs(response, topic=topic)

            # Prevent duplicates within a topic.
            existing_question_texts = {
                question["question"].strip().casefold()
                for question in generated_questions
            }

            for question in new_questions:
                normalized_question = question["question"].strip().casefold()

                if normalized_question in existing_question_texts:
                    continue

                generated_questions.append(question)
                existing_question_texts.add(normalized_question)

                if len(generated_questions) >= target:
                    break

        topic_to_questions[topic].extend(generated_questions)
        all_questions.extend(generated_questions)

        if len(generated_questions) < target:
            st.warning(
                f"Could not generate enough valid questions for {topic}: "
                f"{len(generated_questions)}/{target}"
            )

    return all_questions, topic_to_questions


# ============================================================
# Assessment utilities
# ============================================================

def calculate_scores(mcqs, user_answers):
    """Calculate total score and topic-wise performance."""
    topic_scores = defaultdict(lambda: {"correct": 0, "total": 0})
    total_score = 0

    for index, mcq in enumerate(mcqs):
        topic = mcq.get("topic", "Unknown")
        selected_answer = user_answers[index]

        topic_scores[topic]["total"] += 1

        correct_index = ord(mcq["correct"]) - ord("a")
        correct_text = mcq["options"][correct_index]

        if selected_answer == correct_text:
            topic_scores[topic]["correct"] += 1
            total_score += 1

    return total_score, topic_scores


def submit_assessment():
    """Evaluate the current answers and store the result."""
    mcqs = st.session_state["mcqs"]
    user_answers = st.session_state["user_answers"]

    score, topic_scores = calculate_scores(mcqs, user_answers)

    st.session_state["score"] = score
    st.session_state["topic_scores"] = topic_scores
    st.session_state["submitted"] = True


# ============================================================
# Streamlit UI
# ============================================================

st.set_page_config(page_title="MCQ Assessment")
st.header("MCQ Assessment with Generative AI")

content = st.text_area(
    "Enter content with topics for generating MCQs:",
    height=200,
)

if st.button("Generate Assessment"):
    if not content.strip():
        st.error("Content cannot be empty.")
    else:
        with st.spinner("Parsing content and generating questions..."):
            topics = parse_content_by_topic(content)

            if not topics:
                st.error("No valid topics were found.")
            else:
                all_mcqs, topic_to_questions = generate_mcqs_per_topic(topics)

                if all_mcqs:
                    st.session_state["mcqs"] = all_mcqs
                    st.session_state["topic_to_questions"] = topic_to_questions
                    st.session_state["user_answers"] = [None] * len(all_mcqs)
                    st.session_state["submitted"] = False
                    st.session_state["score"] = 0
                    st.session_state["topic_scores"] = defaultdict(
                        lambda: {"correct": 0, "total": 0}
                    )
                    st.session_state["start_time"] = time.time()
                    st.session_state["time_limit"] = TIME_LIMIT_SECONDS

                    st.success(
                        f"Assessment generated with {len(all_mcqs)} valid questions."
                    )
                else:
                    st.error(
                        "Failed to generate valid questions. "
                        "Please check the input content and try again."
                    )


# ============================================================
# Timer
# ============================================================

def display_timer():
    """Display remaining time and return whether the assessment is active."""
    if "start_time" not in st.session_state:
        return False

    elapsed_time = time.time() - st.session_state["start_time"]
    remaining_time = st.session_state["time_limit"] - elapsed_time

    if remaining_time <= 0:
        st.error("Time is up! Your answers will be submitted automatically.")
        return False

    minutes, seconds = divmod(int(remaining_time), 60)
    st.info(f"Time remaining: {minutes:02d}:{seconds:02d}")
    return True


# ============================================================
# Conduct assessment
# ============================================================

if "mcqs" in st.session_state and not st.session_state.get("submitted", False):
    if display_timer():
        st.subheader("Take the Assessment")

        mcqs = st.session_state["mcqs"]

        for index, mcq in enumerate(mcqs):
            st.write(f"Q{index + 1}: {mcq['question']}")

            selected_answer = st.radio(
                f"Select your answer for Q{index + 1}:",
                [""] + mcq["options"],
                index=0,
                key=f"q{index + 1}",
            )

            st.session_state["user_answers"][index] = selected_answer

        if st.button("Submit Assessment"):
            submit_assessment()
            st.rerun()


# ============================================================
# Automatic submission after timeout
# ============================================================

if (
    "mcqs" in st.session_state
    and "start_time" in st.session_state
    and not st.session_state.get("submitted", False)
):
    elapsed_time = time.time() - st.session_state["start_time"]

    if elapsed_time >= st.session_state["time_limit"]:
        submit_assessment()


# ============================================================
# Final score and feedback
# ============================================================

if st.session_state.get("submitted", False):
    score = st.session_state.get("score", 0)
    mcqs = st.session_state.get("mcqs", [])

    st.write(f"Your final score is: {score}/{len(mcqs)}")

    st.subheader("Feedback on Your Performance")

    topic_scores = st.session_state.get("topic_scores", {})

    for topic, scores in topic_scores.items():
        correct = scores["correct"]
        total = scores["total"]
        accuracy = (correct / total) * 100 if total > 0 else 0

        if accuracy >= 85:
            st.success(
                f"You performed well in the topic: "
                f"{topic} ({accuracy:.2f}% accuracy)"
            )
        elif accuracy <= 25:
            st.warning(
                f"You need to improve in the topic: "
                f"{topic} ({accuracy:.2f}% accuracy)"
            )
        else:
            st.info(
                f"You performed moderately in the topic: "
                f"{topic} ({accuracy:.2f}% accuracy)"
            )
