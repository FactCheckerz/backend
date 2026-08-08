# 🧠 Fact Checker — Backend

> **The intelligence behind the verification.**

The **Fact Checker Backend** powers the AI-driven analysis behind the Fact Checker application.

It receives content from the frontend, processes the information, identifies the **claims being made**, and evaluates them against relevant evidence to determine their credibility.

### ✨ What it provides

* 📝 **Claim Detection** — Extracts factual claims from submitted content
* 🔍 **Evidence Retrieval** — Finds relevant information to verify claims
* ✅ **Fact Verification** — Determines whether claims are supported or refuted
* 📊 **Confidence Score** — Provides a confidence percentage for each verdict
* 💡 **Explanation** — Generates understandable reasoning for the result
* 🎙️ **Multimodal Processing** — Supports text, audio, and video inputs

### 🧩 Processing Flow

```text
Text • Audio • Video
        ↓
  Content Processing
        ↓
   Claim Detection
        ↓
 Evidence Retrieval
        ↓
  Fact Verification
        ↓
 Verdict + Confidence
        ↓
 Evidence & Explanation
```

---

## 📁 This Repository

This repository contains the **backend codebase** of Fact Checker, responsible for the application's AI, NLP, and fact-verification processes.

It exposes an API through which the **Next.js frontend** communicates with the backend.

The frontend and backend are maintained as **separate codebases**, allowing the user interface and AI processing system to evolve independently.

---

### 🎓 Academic Project

Developed as part of the **Deep Learning & Natural Language Processing** curriculum.
