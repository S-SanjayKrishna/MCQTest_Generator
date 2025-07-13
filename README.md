
# MCQ Test Generator using Gemini API

A Streamlit-based web application that uses Google’s Gemini generative AI to automatically create topic-wise multiple-choice questions (MCQs) from user-provided content. Users can take the test within a time limit, and get topic-wise feedback based on their performance.

## Features:

-  **AI-Generated Questions**: Uses Google Gemini 1.5 Flash to generate high-quality MCQs.
-  **Topic-Aware Parsing**: Parses your input content into separate topics.
-  **Dynamic MCQ Allocation**: Automatically assigns a balanced number of questions per topic.
-  **30-Minute Timer**: Countdown timer for completing the test.
-  **Auto-Submit on Timeout**: Automatically submits the test when time is up.
-  **Topic-Based Performance Feedback**: Provides detailed feedback per topic after submission.

---

##  Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python
- **AI Model**: Google Gemini 1.5 Flash

---

##  How It Works

1. **Input**  
   Paste content into the text area, structured with topic headers ending in `:` followed by their respective descriptions.

2. **MCQ Generation**  
   The app uses the Gemini AI model to generate multiple-choice questions (MCQs) with four options per question. The correct answer is embedded as metadata.

3. **Test UI**  
   The generated questions are presented to the user with interactive radio buttons for answer selection.

4. **Timer**  
   A countdown timer of 30 minutes is started once the assessment begins. Users must complete the test within the time limit.

5. **Evaluation**  
   After submission (manual or auto), answers are evaluated and a score is calculated. Topic-wise accuracy and feedback are also displayed.

---

## 📄 Output

- Questions generated for each topic based on the provided content
- Interactive user interface for selecting answers
- Automatic submission of responses after 30 minutes
- Final score display with detailed topic-wise performance feedback


##  Installation

### Prerequisites

- Python 3.7+
- A Google Gemini API key

