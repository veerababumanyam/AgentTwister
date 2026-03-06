---
name: conversational-agent-workbench
description: Use when building or working with the AgentTwister chat interface, conversational AI workbench, streaming agent responses, rich result cards, intent classification, or clarifying questions, agent status rails, or evidence bundles. Triggers for tasks involving chat interface development, streaming responses, real-time agent progress, conversational AI UX, message threading, agent orchestration, or the Chat Orchestrator pattern.
---

# Conversational Agent Workbench

A comprehensive guide for building the AgentTwister conversational chat interface — a human-friendly, streaming chat experience for AI-powered security research.

## Core Principles

The Instant feedback — Token-level streaming; status within 500ms
    Transparency without noise — Collapsible agent thought cards; visible to curious researchers
    Progressive disclosure — Simple questions get simple answers; complex workflows unfold naturally
    Human language first — Users never need to know UC numbers or OWASP codes
    Results in context — Downloadable artifacts, tables, score meters as inline cards

---

## Architecture Overview

```
┌─────────────────┐     ┌────────────────┐
│   Frontend      │────▶│   Chat API      │
│   (React)        │     │   (FastAPI)     │
└────────┬────────┘     └────────┬────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐     ┌────────────────┐
│   WebSocket      │────▶│   LiteLLM      │
│   (Streaming)    │     │   Gateway      │
└────────┬────────┘     └────────┬────────┘
         │                           │
         ▼                           ▼
┌─────────────────┐
│   Firestore      │
│   (Session Store)  │
└─────────────────┘
```

---

## Frontend Components

### Chat Thread
```typescript
// frontend/src/components/ChatThread.tsx
import React, { useState, useEffect } from 'react';
import { VercelChat } from '@ai-sdk/vercel-chat';

interface Message {
  role: 'user' | 'assistant';
  content: string | MessageContent;
}

interface RichResultCard {
  type: 'attack_plan' | 'probe_result' | 'document_download' | 'evidence_bundle';
  data: any;
}

export function ChatThread({ campaignId }: { campaignId: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [richResults, setRichResults] = useState<RichResultCard[]>([]);

  useEffect(() => {
    // Load chat history
    loadChatHistory(campaignId);

    // Setup WebSocket connection
    const ws = new WebSocket(`${WS_URL}/campaigns/${campaignId}/chat`);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'token') {
        // Append token to last message
        setMessages(prev => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage?.role === 'assistant') {
            return [...prev.slice(0, -1), {
              ...lastMessage,
              content: lastMessage.content + data.content
            }];
          }
          return [...prev, { role: 'assistant', content: data.content }];
        });
      } else if (data.type === 'agent_status') {
        setActiveAgent(data.agent);
      } else if (data.type === 'rich_result') {
        setRichResults(prev => [...prev, data]);
      }
    };
  }, [campaignId]);

  return () => ws.close();
  }, [campaignId]);

  const sendMessage = async (content: string) => {
    // Add user message
    setMessages(prev => [...prev, { role: 'user', content }]);
    setIsStreaming(true);

    // Send to backend
    await fetch(`/api/campaigns/${campaignId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: content })
    });
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
      </div>

      <AgentStatusRail agent={activeAgent} />

      <RichResultDisplay results={richResults} />

      <ChatInput onSend={sendMessage} isStreaming={isStreaming} />
    </div>
  );
}
```

---

### Agent Status Rail

```typescript
// frontend/src/components/AgentStatusRail.tsx
import React from 'react';

interface AgentStatusProps {
  agent: string | null;
}

const AGENT_ICONS = {
  analyst: '🔍',
  planner: '📋',
  architect: '🏗️',
  payload_engineer: '⚙️',
  reviewer: '✅',
  formatter: '📄'
};

const AGENT_LABELS = {
  analyst: 'Analyst',
  planner: 'Planner',
  architect: 'Architect',
  payload_engineer: 'Payload Engineer',
  reviewer: 'Reviewer',
  formatter: 'Formatter'
};

export function AgentStatusRail({ agent }: AgentStatusProps) {
  if (!agent) return null;

  return (
    <div className="status-rail">
      <div className="agent-indicator active">
        <span className="icon">{AGENT_ICONS[agent]}</span>
        <span className="label">{AGENT_LABELS[agent]}</span>
        <span className="status">Working...</span>
      </div>
    </div>
  );
}
```

---

### Rich Result Card
```typescript
// frontend/src/components/RichResultCard.tsx
import React from 'react';

interface RichResultProps {
  type: 'attack_plan' | 'probe_result' | 'document_download' | 'evidence_bundle';
  data: any;
}

export function RichResultCard({ type, data }: RichResultProps) {
  const renderers = {
    attack_plan: AttackPlanCard,
    probe_result: ProbeResultCard,
    document_download: DocumentDownloadCard,
    evidence_bundle: EvidenceBundleCard
  };

  const Renderer = renderers[type];
  return Renderer ? <Renderer data={data} /> : null;
}

}

function AttackPlanCard({ data }: { data: any }) {
  return (
    <div className="result-card attack-plan">
      <h4>Attack Plan</h4>
      <div className="plan-items">
        {data.attackVectors.map((vector: any, i: number) => (
          <div key={i} className="plan-item">
            <span className="vector-name">{vector.name}</span>
            <span className={`impact ${vector.impact}`}>
              {vector.impact}
            </span>
            <span className="actions">
              {vector.actions.join(', ')}
            </span>
          </div>
        ))}
      </div>
      <div className="actions">
        <button>Appro All</button>
        <button>Customize</button>
      </div>
    </div>
  );
}

function ProbeResultCard({ data }: { data: any }) {
  return (
    <div className="result-card probe-result">
      <h4>Endpoint Probe Results</h4>
      <div className="probe-summary">
        <span className="payload-sent">{data.payloadsSent} payloads sent</span>
        <span className="responses">{data.responses} responses</span>
        <span className={`verdict ${data.verdict}`}>
          {data.verdict}
        </span>
      </div>
      <pre className="response-excerpt">
        {data.responseExcerpt}
      </pre>
    </div>
  );
}

function DocumentDownloadCard({ data }: { data: any }) {
  return (
    <div className="result-card document-download">
      <h4>Document Ready</h4>
      <div className="document-preview">
        <span className="filename">{data.filename}</span>
        <span className="payload-count">{data.payloadCount} payloads</span>
        <span className="stealth-score">Stealth: {data.stealthScore}/5.0</span>
      </div>
      <button className="download-btn">
        Download {data.fileType.toUpperCase()}
      </button>
    </div>
  );
}

function EvidenceBundleCard({ data }: { data: any }) {
  return (
    <div className="result-card evidence-bundle">
      <h4>Evidence Bundle</h4>
      <div className="evidence-summary">
        <span className="campaign-id">Campaign: {data.campaignId}</span>
        <span className="artifacts">{data.artifactCount} artifacts</span>
        <span className="signatures">{data.signatureCount} signatures</span>
      </div>
      <button className="export-btn">
        Export Bundle (JSON + PDF)
      </button>
    </div>
  );
}
```

---

## Backend API

### Chat Endpoints
```python
# backend/app/api/routes/chat.py
from fastapi import APIRouter, WebSocket
from pydantic import BaseModel
from typing import List

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

@router.post("/campaigns/{campaign_id}/chat")
async def send_chat_message(campaign_id: str, message: ChatMessage):
    """Send a chat message and trigger agent pipeline."""
    # 1. Store message in Firestore
    await store_message(campaign_id, message)

    # 2. Classify intent via Chat Orchestrator
    intent = await chat_orchestrator.classify_intent(
        message.content,
        await get_context(campaign_id)
    )

    # 3. If confidence < 0.8, ask clarifying questions
    if intent.confidence < 0.8:
        return {
            "type": "clarification",
            "questions": intent.clarifying_questions
        }

    # 4. Otherwise, dispatch to appropriate agent
    result = await dispatch_to_agent(campaign_id, intent)

    return {"type": "result", "data": result}

@router.websocket("/campaigns/{campaign_id}/ws")
async def chat_websocket(websocket: WebSocket, campaign_id: str):
    """WebSocket endpoint for streaming responses."""
    await websocket.accept()

    # Subscribe to campaign updates
    async for message in subscribe_to_campaign(campaign_id):
        if message["type"] == "token":
            await websocket.send_json({
                "type": "token",
                "content": message["content"]
            })
        elif message["type"] == "agent_status":
            await websocket.send_json({
                "type": "agent_status",
                "agent": message["agent"]
            })
        elif message["type"] == "rich_result":
            await websocket.send_json({
                "type": "rich_result",
                "resultType": message["resultType"],
                "data": message["data"]
            })
```

---

## Streaming Implementation

### Token-Level Streaming
```python
# backend/app/services/streaming.py
import asyncio
from typing import AsyncGenerator
from google.adk.streaming import stream_response

async def stream_agent_response(
    agent: BaseAgent,
    prompt: str,
    campaign_id: str
) -> AsyncGenerator[str, None]:
    """
    Stream agent response token by token.
    Yields tokens and publishes to campaign subscribers.
    """
    full_response = ""

    async for token in stream_response(agent, prompt):
        full_response += token

        # Publish token to WebSocket subscribers
        await publish_to_campaign(campaign_id, {
            "type": "token",
            "content": token
        })

        yield token

    return full_response
```

### Agent Status Streaming
```python
async def stream_agent_status(
    agent_name: str,
    status: str,
    campaign_id: str
) -> None:
    """Publish agent status update to campaign subscribers."""
    await publish_to_campaign(campaign_id, {
        "type": "agent_status",
        "agent": agent_name,
        "status": status
    })
```

### Rich Result Streaming
```python
async def stream_rich_result(
    result_type: str,
    data: dict,
    campaign_id: str
) -> None:
    """Publish rich result card to campaign subscribers."""
    await publish_to_campaign(campaign_id, {
        "type": "rich_result",
        "resultType": result_type,
        "data": data
    })
```

---

## Intent Classification

The Chat Orchestrator classifies user intent into categories:

```python
# backend/app/agents/chat_orchestrator.py
from typing import Literal, List
from pydantic import BaseModel

class IntentClassification(BaseModel):
    intent: Literal[
        "start_campaign",
        "refine_plan",
        "answer_question",
        "generate_payloads",
        "run_probe",
        "export_results"
    ]
    confidence: float
    clarifying_questions: List[str] = []

class ChatOrchestrator(BaseAgent):
    async def classify_intent(
        self,
        message: str,
        context: dict
    ) -> IntentClassification:
        """
        Classify user message intent for routing.

        Uses LLM to understand what the user wants to do.
        """
        prompt = f"""
        Analyze this user message and classify the intent.

        Context: {json.dumps(context)}
        Message: {message}

        Valid intents:
        - start_campaign: User wants to begin a new security test
        - refine_plan: User wants to modify an existing attack plan
        - answer_question: User is asking for help/information
        - generate_payloads: User wants to generate adversarial payloads
        - run_probe: User wants to test an endpoint
        - export_results: User wants to download/export results

        Return JSON with:
        - intent: one of the valid intents
        - confidence: 0.0-1.0 (how confident you are)
        - clarifying_questions: list of questions if confidence < 0.8

        EXAMPLE OUTPUT:
        {{
            "intent": "start_campaign",
            "confidence": 0.95,
            "clarifying_questions": []
        }}
        """

        response = await self.llm_generate(
            prompt,
            system_prompt=INTENT_CLASSIFICATION_PROMPT,
            temperature=0.3
        )

        return IntentClassification.model_validate_json(response)
```

---

## UX Flow: Chat-Driven Campaign

```
User:  "I want to test our new AI-powered HR screening tool for prompt injection.
        It's a RAG-based system that reads resumes and scores candidates.
        We own the system — I have authorization."

  ↳ [Chat Orchestrator] classifies intent: "start_campaign"

  ↳ [Chat Orchestrator] streams: "Got it! I'll focus on indirect prompt injection
     via the resume and potential RAG poisoning vectors. Quick question:
     do you have a sample job description I can tailor the payloads to?"

User:  [drags and drops JD.pdf into chat]

  ↳ [Chat Orchestrator] streams: "Perfect. Starting the analysis now."
  ↳ [Status Rail] shows: "Analyst · Reading job description..."
  ↳ [Status Rail] updates: "Planner · Selecting attack vectors... (3/7 done)"
  ↳ [Chat] renders Attack Plan Card:
       ✅ UC-01 Direct Prompt Injection  (Impact: High)     [Approve] [Skip]
       ✅ UC-06 RAG Poisoning            (Impact: High)     [Approve] [Skip]
       ✅ UC-11 Adversarial Resume       (Impact: Critical) [Approve] [Skip]

User:  [Approves all three]

  ↳ [Status Rail]: "Architect · Planning payload placements..."
  ↳ [Status Rail]: "Payload Engineer · Embedding 6 payloads..."
  ↳ [Status Rail]: "Reviewer · Stealth score: 4.8/5.0 ✓"
  ↳ [Status Rail]: "Formatter · Building DOCX + PDF..."
  ↳ [Chat] renders Document Result Card:
       📄 adversarial_resume_v1.docx
       Stealth Score: ████████→ 4.8/5.0
       Payloads embedded: 6   OWASP: LLM01, LLM03, ASI-04
       [Download DOCX] [Download PDF]
```

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Instant Feedback** | Token-level streaming; agent status within 500ms |
| **Transparency** | Collapsible agent thought cards |
| **Progressive Disclosure** | Simple → complex workflows unfold naturally |
| **Human Language** | No UC numbers, OWASP codes, or agent names |
| **Results in Context** | Inline rich result cards, no navigation |

---

## Checklist: Adding Chat Features
1. [ ] Create ChatThread component with message list
2. [ ] Implement WebSocket connection for streaming
3. [ ] Create AgentStatusRail component
4. [ ] Create RichResultCard components for each result type
5. [ ] Implement intent classification in Chat Orchestrator
6. [ ] Add clarifying question flow for low-confidence intents
7. [ ] Create streaming service for token publishing
8. [ ] Add file upload support for drag-and-drop
9. [ ] Implement chat history loading
10. [ ] Add export functionality for results

---

## File Locations Reference
| Component | Location |
|-----------|----------|
| Chat Thread | `frontend/src/components/ChatThread.tsx` |
| Agent Status Rail | `frontend/src/components/AgentStatusRail.tsx` |
| Rich Result Cards | `frontend/src/components/RichResultCard.tsx` |
| Chat API Routes | `backend/app/api/routes/chat.py` |
| Streaming Service | `backend/app/services/streaming.py` |
| Chat Orchestrator | `backend/app/agents/chat_orchestrator.py` |
| WebSocket Handler | `backend/app/api/websocket.py` |
