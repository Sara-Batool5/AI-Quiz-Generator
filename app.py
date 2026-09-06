import json
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import pypdf

# ------------------------------------------------------------------------------
# 1. Page Config & Session State Initialization
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Study Material → Quiz Generator",
    page_icon="🎓",
    layout="wide",
)

if "quiz_data" not in st.session_state:
    st.session_state.quiz_data = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "quiz_submitted" not in st.session_state:
    st.session_state.quiz_submitted = False

# ------------------------------------------------------------------------------
# 2. Schema Definition for Gemini Structured Output
# ------------------------------------------------------------------------------
class Question(BaseModel):
    id: int = Field(description="Unique question index starting from 1")
    question: str = Field(description="The question text")
    type: str = Field(description="Type of question: MCQ, True/False, or Short Question")
    options: list[str] = Field(
        default=[],
        description="List of choices for MCQ (4 choices) or True/False (['True', 'False']). Empty for Short Question."
    )
    correct_answer: str = Field(description="Exact string matching the correct option or ideal short answer")
    explanation: str = Field(description="Brief explanation of why the answer is correct based on the text")

class QuizSchema(BaseModel):
    questions: list[Question]

# ------------------------------------------------------------------------------
# 3. Helper Functions
# ------------------------------------------------------------------------------
def extract_text_from_pdf(uploaded_file) -> str:
    reader = pypdf.PdfReader(uploaded_file)
    extracted_text = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted_text += text + "\n"
    return extracted_text

def generate_quiz(api_key: str, text: str, num_questions: int, difficulty: str, q_types: list) -> QuizSchema:
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are an expert tutor. Analyze the following study material and generate a quiz tailored specifically to its content.
    
    Requirements:
    - Total Questions: {num_questions}
    - Difficulty Level: {difficulty}
    - Allowed Question Types: {', '.join(q_types)}
    
    Study Material Content:
    {text[:20000]}  # Truncated to fit safe context window limit
    """

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QuizSchema,
            temperature=0.3,
        ),
    )
    
    return QuizSchema.model_validate_json(response.text)

# ------------------------------------------------------------------------------
# 4. Streamlit UI Components
# ------------------------------------------------------------------------------
st.title("🎓 AI Study Material → Quiz Generator")
st.write("Upload your notes or PDF, select preferences, and generate a customized practice test!")

# Sidebar - Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Gemini API Key", type="password", help="Enter your Google AI Studio API Key")
    
    uploaded_file = st.file_uploader("Upload Notes (PDF or TXT)", type=["pdf", "txt"])
    
    num_questions = st.number_input("Number of Questions", min_value=1, max_value=20, value=5)
    difficulty = st.selectbox("Difficulty Level", ["Easy", "Medium", "Hard"])
    q_types = st.multiselect(
        "Question Types",
        ["MCQ", "True/False", "Short Question"],
        default=["MCQ", "True/False"]
    )
    
    generate_btn = st.button("✨ Generate Quiz", type="primary", use_container_width=True)

# Generate Logic
if generate_btn:
    if not api_key:
        st.error("Please enter your Gemini API Key in the sidebar.")
    elif not uploaded_file:
        st.error("Please upload a PDF or TXT file.")
    elif not q_types:
        st.error("Please select at least one question type.")
    else:
        with st.spinner("Extracting material and generating questions..."):
            try:
                # Extract text
                if uploaded_file.name.endswith(".pdf"):
                    raw_text = extract_text_from_pdf(uploaded_file)
                else:
                    raw_text = uploaded_file.read().decode("utf-8")

                if not raw_text.strip():
                    st.error("Could not extract readable text from the uploaded file.")
                else:
                    # Generate quiz
                    quiz_response = generate_quiz(api_key, raw_text, num_questions, difficulty, q_types)
                    st.session_state.quiz_data = quiz_response.questions
                    st.session_state.user_answers = {}
                    st.session_state.quiz_submitted = False
                    st.success("Quiz generated successfully!")
            except Exception as e:
                st.error(f"Error generating quiz: {e}")

# ------------------------------------------------------------------------------
# 5. Display Quiz & Interactive Mode
# ------------------------------------------------------------------------------
if st.session_state.quiz_data:
    tab1, tab2 = st.tabs(["📝 Take Quiz Mode", "📜 Complete Answer Key"])

    # --- TAB 1: Take Quiz Mode ---
    with tab1:
        st.subheader("Interactive Quiz")
        
        with st.form("quiz_form"):
            for i, q in enumerate(st.session_state.quiz_data):
                st.markdown(f"**Q{i+1}. [{q.type}] {q.question}**")
                
                if q.type in ["MCQ", "True/False"]:
                    st.session_state.user_answers[q.id] = st.radio(
                        f"Select your answer for Q{i+1}:",
                        options=q.options,
                        key=f"q_{q.id}",
                        index=None,
                        label_visibility="collapsed"
                    )
                elif q.type == "Short Question":
                    st.session_state.user_answers[q.id] = st.text_input(
                        f"Type your short answer for Q{i+1}:",
                        key=f"q_{q.id}",
                        label_visibility="collapsed"
                    )
                st.divider()

            submit_quiz = st.form_submit_button("Submit Answers", type="primary")

        if submit_quiz:
            st.session_state.quiz_submitted = True

        if st.session_state.quiz_submitted:
            st.markdown("---")
            st.header("📊 Quiz Results")
            score = 0
            auto_gradable_total = 0

            for q in st.session_state.quiz_data:
                user_ans = st.session_state.user_answers.get(q.id)
                st.markdown(f"**Q{q.id}: {q.question}**")

                if q.type in ["MCQ", "True/False"]:
                    auto_gradable_total += 1
                    if user_ans and user_ans.strip().lower() == q.correct_answer.strip().lower():
                        score += 1
                        st.success(f"✅ Your Answer: {user_ans} (Correct)")
                    else:
                        st.error(f"❌ Your Answer: {user_ans if user_ans else 'No answer provided'}")
                        st.info(f"**Correct Answer:** {q.correct_answer}")
                else:
                    st.warning(f"✍️ Your Answer: {user_ans if user_ans else 'No answer provided'}")
                    st.info(f"**Sample Ideal Answer:** {q.correct_answer}")

                st.caption(f"💡 **Explanation:** {q.explanation}")
                st.markdown("---")

            if auto_gradable_total > 0:
                st.metric("Final Score (Objective Questions)", f"{score} / {auto_gradable_total}")

    # --- TAB 2: Complete Answer Key ---
    with tab2:
        st.subheader("Answer Key & Explanations")
        for q in st.session_state.quiz_data:
            st.markdown(f"**Q{q.id} ({q.type}): {q.question}**")
            if q.options:
                st.write(f"*Options:* {', '.join(q.options)}")
            st.markdown(f"**Correct Answer:** `{q.correct_answer}`")
            st.markdown(f"**Explanation:** {q.explanation}")
            st.divider()
