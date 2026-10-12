# Submission and progressive hints implementation plan

Goal: connect the existing two Python lessons to deterministic server judging and evidence-based Ollama hints.

The user's eight requirements are the approved scope. Reuse the existing sandbox and CodeEditor. No generated exercises, model training, new AST diagnosis, or misconception database. Existing account/login work must remain intact.

- [x] Verify installed qwen2.5-coder:3b-instruct through the Docker backend.
- [x] Add failing backend tests for authoritative problem IDs, accepted submissions skipping AI, three failure types, malformed/model-error/timeout responses, evidence validation, and execution deadlines.
- [x] Reuse Sandbox in a child process with a parent deadline and bounded output. Apply to run and submit routes. This is execution control, not a secure public code hosting sandbox.
- [x] Define the current level1/level2 questions and stdout test cases on the server. Preserve trim-based output comparison. Each existing task has one no-input test; do not claim algorithm or code-style verification.
- [x] Add authenticated POST /api/v1/code/submit accepting only problem_id and code. Return typed judge facts independently from analysis state. Reject unknown problems and client-supplied expected outputs.
- [x] Only on failed judging: send question, submitted code and observed evidence to Ollama with a JSON schema. Validate schema, cited evidence, and no solution/code blocks. Return ready/skipped/unavailable/timeout/invalid_response; preserve judge facts on any model failure.
- [x] Adapt CodeEditor submission and add sequential reveal of three hints. Reset old feedback on edits and resubmission; remove the lesson's static answer leak.
- [x] Verify three different wrong submissions with the real model, plus a correct submission, actual API and browser interaction. Record facts and semantic review of model analysis.
- [x] Run backend regression suite, frontend build, Docker configuration/build and health checks. Review changes and document startup, API fields, file responsibilities and test commands.

Backend files: app/api/coding.py (routes), app/services/submission.py (problem registry and judge models), app/services/error_analysis.py (structured model output), app/services/sandbox/runner.py + worker.py (bounded execution), sandbox.py (bounded capture), tests/test_submission.py and optional live smoke script.

Frontend files: components/CodeEditor.jsx, components/SubmissionFeedback.jsx if useful, pages/Level1.jsx and Level2.jsx, relevant CSS. Deployment: frontend/nginx.conf model-wait timeout if necessary. README and docs record reproducible evidence.

Acceptance boundary: the real API/browser flow is operational. Exact evidence citations passed, but live Qwen 3B hints still show premature disclosure, repetition and irrelevant hypotheses. See docs/submission-flow.md for the human semantic review; stable teaching quality is not claimed.
