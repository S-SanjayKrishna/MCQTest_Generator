# MCQ Test Generator using Gemini API

A Streamlit-based web application that uses Google's Gemini API to automatically generate topic-wise multiple-choice assessments from user-provided content. The application includes resilient API handling, validated LLM-output parsing, timed assessments, automated scoring, and topic-wise performance feedback.

## Features

* **AI-Generated Questions**: Uses Google Gemini to generate topic-specific MCQs.
* **Topic-Aware Parsing**: Parses user-provided content into separate topics and their associated details.
* **Balanced Question Allocation**: Distributes a target of 30 questions as evenly as possible across the available topics.
* **Resilient API Integration**: Uses bounded retries with exponential backoff and randomized jitter to handle transient Gemini API failures.
* **Validated LLM Output Parsing**: Extracts and validates questions, four options, and correct-answer metadata from Gemini's text responses.
* **Duplicate Prevention**: Prevents duplicate questions from being added within a topic during retry attempts.
* **30-Minute Timer**: Provides a timed assessment experience.
* **Automatic Submission**: Evaluates the user's answers when the time limit is reached.
* **Topic-Based Performance Feedback**: Calculates overall score and topic-wise accuracy.

## Tech Stack

* **Frontend/UI**: Streamlit
* **Backend**: Python
* **Generative AI**: Google Gemini API
* **Environment Management**: python-dotenv
* **Parsing & Validation**: Python Regular Expressions

## How It Works

### 1. Input

The user enters content organized into topics. Topic headings are provided using a `:` suffix, followed by the relevant topic details.

### 2. Topic Parsing

The application separates topic headings from their associated details and stores them as structured topic-detail pairs.

### 3. Question Allocation

The application distributes a target of 30 questions across the available topics as evenly as possible.

### 4. MCQ Generation

A dynamic prompt is created for each topic based on:

* Topic name
* Topic details
* Number of questions required

The prompt is sent to the Gemini API, which generates multiple-choice questions containing four options and the correct-answer metadata.

### 5. Retry and Recovery

The Gemini API integration uses bounded retries to handle transient failures. Retry delays use exponential backoff combined with randomized jitter to avoid repeatedly sending requests at fixed intervals.

### 6. Output Parsing

Gemini's text response is parsed and validated before the questions are added to the assessment.

The parser:

* Identifies individual question blocks.
* Extracts the question text.
* Extracts four answer options.
* Extracts the correct-answer label.
* Normalizes common formatting variations.
* Rejects malformed question blocks.
* Prevents duplicate questions within a topic.

### 7. Assessment

Valid questions are displayed through Streamlit radio buttons. Users can select one answer for each question while a 30-minute assessment timer tracks the remaining time.

### 8. Evaluation

After manual submission or timeout:

* Answers are evaluated automatically.
* The overall score is calculated.
* Topic-wise correct and total answers are calculated.
* Topic-wise accuracy is displayed.
* Performance feedback is provided based on the calculated accuracy.

## Output

The application provides:

* Topic-wise AI-generated MCQs
* Four options for each question
* Interactive timed assessment
* Automatic submission after the time limit
* Overall assessment score
* Topic-wise accuracy
* Topic-based performance feedback

## Installation

### Prerequisites

* Python 3.7+
* Google Gemini API key

### Install Dependencies

```bash
pip install streamlit python-dotenv google-genai
```

### Configure API Key

Create a `.env` file in the project directory:

```text
GOOGLE_API_KEY=your_api_key_here
```

### Run the Application

```bash
streamlit run Finalmcq_L3_Improved.py
```

## Example Input Format

```text
Data Structures:
Arrays, linked lists, stacks, queues, and trees.

Operating Systems:
Processes, threads, CPU scheduling, and memory management.

Database Management:
SQL, normalization, transactions, and indexing.
```

The application parses the topics and generates questions independently for each topic.

## Project Architecture

```text
User Input
    |
    v
Streamlit Interface
    |
    v
Topic Parser
    |
    v
Question Allocation
    |
    v
Prompt Builder
    |
    v
Gemini API
    |
    +---- API Failure
    |        |
    |        v
    |   Exponential Backoff
    |        +
    |      Jitter
    |        |
    |        +---- Retry
    |
    v
LLM Output
    |
    v
MCQ Parser & Validator
    |
    v
Structured MCQ Objects
    |
    v
Timed Assessment
    |
    v
Scoring Engine
    |
    v
Topic-wise Feedback
```
