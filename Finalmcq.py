import os
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
import time
from collections import defaultdict

# Load API key and configure the model
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

# MCQ prompt template
MCQ_PROMPT_TEMPLATE = """
Generate exactly {num_questions} multiple-choice questions from the following topic.
Each question must have exactly 4 options and include the correct answer hidden as metadata at the end of the question block.
Format each question as follows:

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

# Function to generate a formatted prompt for each topic
def generate_prompt(topic, details, num_questions):
    return MCQ_PROMPT_TEMPLATE.format(topic=topic, details=details, num_questions=num_questions)

# Function to get response from Gemini model
def get_gemini_response(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Error generating response from Gemini model: {e}")
        return ""

# Function to parse the content into topics
def parse_content_by_topic(content):
    topics = defaultdict(list)
    lines = content.strip().split("\n")
    current_topic = None
    for line in lines:
        line = line.strip()
        if line:  # Non-empty line
            if not current_topic or line[-1] == ":":  # Topic title ends with ':'
                current_topic = line[:-1].strip()
            else:
                topics[current_topic].append(line)
    return {topic: " ".join(details) for topic, details in topics.items()}

# Function to generate MCQs for each topic with retries
def generate_mcqs_per_topic(topics):
    total_topics = len(topics)
    questions_per_topic = max(1, 30 // total_topics)  # Ensure at least 1 question per topic
    all_questions = []
    topic_to_questions = defaultdict(list)

    for topic, details in topics.items():
        generated_questions = []
        for attempt in range(3):  # Retry up to 3 times to generate sufficient questions
            remaining_questions = questions_per_topic - len(generated_questions)
            if remaining_questions <= 0:
                break
            prompt = generate_prompt(topic, details, num_questions=remaining_questions)
            response = get_gemini_response(prompt)
            new_questions = parse_mcqs(response)
            generated_questions.extend(new_questions[:remaining_questions])

        topic_to_questions[topic].extend(generated_questions)
        all_questions.extend(generated_questions)

        if len(generated_questions) < questions_per_topic:
            st.warning(f"Could not generate enough questions for topic: {topic} (Generated {len(generated_questions)}/{questions_per_topic})")

    return all_questions, topic_to_questions

# Function to parse MCQs from the response text
def parse_mcqs(mcq_text):
    questions = []
    for q in mcq_text.split("\n\n"):  # Assume each question is separated by two newlines
        if q.strip():
            parts = q.split("\n")  # Split by newlines
            if len(parts) >= 6:  # Expect question + 4 options + correct answer
                question = parts[0]
                options = [opt.strip() for opt in parts[1:5]]  # First 4 lines are options
                options = [opt.split(") ", 1)[-1] for opt in options]  # Remove "a)", "b)" prefixes
                correct_answer_line = parts[5].strip()
                if correct_answer_line.lower().startswith("correct:"):
                    correct_answer = correct_answer_line.split(":", 1)[-1].strip()
                    if correct_answer not in ["a", "b", "c", "d"]:
                        continue
                else:
                    continue
                questions.append({"question": question, "options": options, "correct": correct_answer})
    return questions

# Streamlit app setup
st.set_page_config(page_title="MCQ Assessment")
st.header("MCQ Assessment with Generative AI")

# Input content for MCQ generation
content = st.text_area("Enter content with topics for generating MCQs:", height=200)

if st.button("Generate Assessment"):
    if content.strip():
        with st.spinner("Parsing content and generating questions..."):
            topics = parse_content_by_topic(content)
            all_mcqs, topic_to_questions = generate_mcqs_per_topic(topics)

            if all_mcqs:
                st.session_state["mcqs"] = all_mcqs
                st.session_state["topic_to_questions"] = topic_to_questions
                st.session_state["user_answers"] = [None] * len(all_mcqs)
                st.session_state["submitted"] = False
                st.session_state["start_time"] = time.time()
                st.session_state["time_limit"] = 30 * 60  # 30 minutes
                st.success("Assessment generated successfully!")
            else:
                st.error("Failed to generate questions. Please check the input content.")
    else:
        st.error("Content cannot be empty.")


# Timer logic
def display_timer():
    if "start_time" in st.session_state:
        elapsed_time = time.time() - st.session_state["start_time"]
        remaining_time = st.session_state["time_limit"] - elapsed_time
        if remaining_time <= 0:
            st.error("Time is up! Submitting your answers automatically.")
            return False
        else:
            mins, secs = divmod(remaining_time, 60)
            st.info(f"Time remaining: {int(mins):02d}:{int(secs):02d}")
            return True
    return False

# Conduct Assessment
if "mcqs" in st.session_state:
    if display_timer():
        st.subheader("Take the Assessment")
        mcqs = st.session_state["mcqs"]
        for i, mcq in enumerate(mcqs):
            st.write(f"Q{i+1}: {mcq['question']}")
            st.session_state["user_answers"][i] = st.radio(
                f"Select your answer for Q{i+1}:",
                [""] + mcq["options"],
                index=0,
                key=f"q{i+1}"
            )

        if st.button("Submit Assessment"):
            # Evaluate the assessment
            topic_scores = defaultdict(lambda: {"correct": 0, "total": 0})
            total_score = 0

            for i, mcq in enumerate(mcqs):
                selected_answer = st.session_state["user_answers"][i]
                correct_option = mcq["correct"]
                topic = next((t for t, qs in st.session_state["topic_to_questions"].items() if mcq in qs), None)

                if topic:
                    topic_scores[topic]["total"] += 1
                    if selected_answer == mcq["options"][ord(correct_option) - ord("a")]:
                        topic_scores[topic]["correct"] += 1
                        total_score += 1

            st.session_state["score"] = total_score
            st.session_state["submitted"] = True
            st.session_state["topic_scores"] = topic_scores

# Auto-submit when time is up
if "start_time" in st.session_state and not display_timer():
    if not st.session_state.get("submitted", False):
        st.session_state["submitted"] = True
        st.session_state["score"] = sum(
            1 for i, mcq in enumerate(st.session_state["mcqs"])
            if st.session_state["user_answers"][i] in mcq["options"]
            and st.session_state["user_answers"][i] == mcq["options"][ord(mcq["correct"]) - ord('a')]
        )

# Display Final Score and Feedback
if st.session_state.get("submitted", False):
    st.write(f"Your final score is: {st.session_state['score']}/{len(st.session_state['mcqs'])}")

    st.subheader("Feedback on Your Performance")
    topic_scores = st.session_state["topic_scores"]
    for topic, scores in topic_scores.items():
        correct, total = scores["correct"], scores["total"]
        accuracy = (correct / total) * 100 if total > 0 else 0
        if accuracy >= 85:
            st.success(f"You performed well in the topic: {topic} ({accuracy:.2f}% accuracy)")
        elif accuracy <= 25:
            st.warning(f"You need to improve in the topic: {topic} ({accuracy:.2f}% accuracy)")
        else:
            st.info(f"You performed moderately in the topic: {topic} ({accuracy:.2f}% accuracy)")
