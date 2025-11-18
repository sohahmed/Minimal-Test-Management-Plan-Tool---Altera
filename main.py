from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import io

from transformers import pipeline

# Llama-like model: Open LLaMA 3B v2 (smaller and lighter for local CPU use)
llama_generator = pipeline(
    "text-generation",
    model="openlm-research/open_llama_3b_v2",
    device="cpu",  # Set to 0 if using a CUDA GPU
    max_new_tokens=196,
    do_sample=True,
    temperature=0.7,
    top_p=0.95,
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

class TestStep(BaseModel):
    description: str

class TestPlan(BaseModel):
    id: int
    title: str
    description: str
    steps: List[TestStep] = []

class SuggestResponse(BaseModel):
    title: str
    description: str
    steps: List[str]

db = []
plan_id = 1

def extract_text_from_file(file: UploadFile):
    filename = file.filename.lower()
    if filename.endswith('.txt'):
        return file.file.read().decode('utf-8')
    elif filename.endswith('.pdf'):
        import PyPDF2
        pdf = PyPDF2.PdfReader(file.file)
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    elif filename.endswith('.docx'):
        from docx import Document
        docx_bytes = io.BytesIO(file.file.read())
        doc = Document(docx_bytes)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")

def llama_generate_title(text):
    prompt = f"Generate a concise test plan title for the following requirement:\n{text}\nTitle:"
    response = llama_generator(prompt, num_return_sequences=1)[0]['generated_text']
    # Extract line after 'Title:'
    after = response.split("Title:")[-1].strip()
    title = after.split('\n')[0].replace('Title:', '').strip()
    if not title:
        title = "Test Plan"
    return title

def llama_generate_description(text):
    prompt = f"Summarize the following requirement in 1–2 sentences:\n{text}\nSummary:"
    response = llama_generator(prompt, num_return_sequences=1)[0]['generated_text']
    after = response.split("Summary:")[-1]
    desc = after.split('\n')[0].replace('Summary:', '').strip()
    if not desc:
        desc = text.strip()[:130]
    return desc

def llama_generate_steps(text):
    prompt = (
        "Given the following software/system requirement, generate a checklist of test steps as a numbered list. "
        "Each step should be a single line starting with 'Verify: ' and summarize what to check, "
        "matching the content and constraints from the requirement.\n"
        "Do not explain, only list steps as 'Verify: ...'\n"
        f"REQUIREMENT:\n{text.strip()}\n"
        "Test Steps:\n"
    )
    response = llama_generator(prompt, num_return_sequences=1)[0]['generated_text']
    # Extract lines with "Verify: ..." after "Test Steps:"
    lines = response.split("Test Steps:")[-1].split('\n')
    steps = []
    for l in lines:
        if "Verify:" in l:
            step = l.split("Verify:", 1)[-1].strip(" .:-")
            steps.append(f"Verify: {step}")
        elif l.strip().startswith("1.") and "Verify:" not in l:
            # Try to fix lines like "1. System accepts valid login" to "Verify: System accepts valid login"
            content = l.split(".", 1)[-1].strip(" .:-")
            if content:
                steps.append(f"Verify: {content}")
        if len(steps) >= 8:
            break
    # Remove duplicates and blanks
    steps = [s for i, s in enumerate(steps) if s and s not in steps[:i]]
    if not steps:
        # fallback: get any decent lines
        from re import findall
        candidates = findall(r'([A-Z][^.!?\n]*\.)', response)
        for c in candidates:
            sc = c.replace('\n', '').strip()
            if sc.lower().startswith('verify:'):
                steps.append(sc)
        steps = steps[:8]
    if not steps:
        steps = ["Could not generate usable steps for this requirement."]
    return steps

@app.get("/testplans", response_model=List[TestPlan])
def list_testplans():
    return db

@app.post("/testplans", response_model=TestPlan)
def create_testplan(plan: TestPlan):
    global plan_id
    plan.id = plan_id
    db.append(plan)
    plan_id += 1
    return plan

@app.get("/testplans/{id}", response_model=TestPlan)
def get_testplan(id: int):
    for p in db:
        if p.id == id:
            return p
    raise HTTPException(status_code=404)

@app.put("/testplans/{id}", response_model=TestPlan)
def update_testplan(id: int, plan: TestPlan):
    for idx, p in enumerate(db):
        if p.id == id:
            db[idx] = plan
            return plan
    raise HTTPException(status_code=404)

@app.delete("/testplans/{id}")
def delete_testplan(id: int):
    global db
    db = [p for p in db if p.id != id]
    return {'success': True}

@app.post("/testplans/{id}/steps", response_model=List[TestStep])
def add_step(id: int, step: TestStep):
    for p in db:
        if p.id == id:
            p.steps.append(step)
            return p.steps
    raise HTTPException(status_code=404)

@app.put("/testplans/{id}/steps/{step_idx}", response_model=TestStep)
def edit_step(id: int, step_idx: int, step: TestStep):
    for p in db:
        if p.id == id and 0 <= step_idx < len(p.steps):
            p.steps[step_idx] = step
            return step
    raise HTTPException(status_code=404)

@app.delete("/testplans/{id}/steps/{step_idx}")
def delete_step(id: int, step_idx: int):
    for p in db:
        if p.id == id and 0 <= step_idx < len(p.steps):
            p.steps.pop(step_idx)
            return {'success': True}
    raise HTTPException(status_code=404)

@app.post("/suggest_file", response_model=SuggestResponse)
async def suggest_steps_from_file(file: UploadFile):
    input_text = extract_text_from_file(file)
    title = llama_generate_title(input_text)
    description = llama_generate_description(input_text)
    steps = llama_generate_steps(input_text)
    return {
        "title": title,
        "description": description,
        "steps": steps
    }