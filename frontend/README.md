# ArchLens: Code Made Clear

Build ArchLens AI — Premium AI Developer Tool Frontend

1. PRODUCT

Build the complete frontend for ArchLens AI, an AI-powered codebase intelligence and architecture visualization platform.

Product tagline

Understand your codebase. Before you touch a single file.

Product concept

ArchLens AI analyzes software repositories and transforms source code into an understandable visual architecture.

The eventual workflow is:

Repository
    ↓
Static Code Analysis
    ↓
Dependency Graph
    ↓
Architecture Inference
    ↓
AI Explanation
    ↓
Architecture Visualization
    ↓
Architecture Health
    ↓
Architecture Diff


The frontend should make this concept visually obvious.

2. IMPORTANT DESIGN DIRECTION

Do NOT create a generic AI SaaS landing page.

Avoid:

Generic purple AI gradients

Generic glowing orb

Generic robot/AI illustrations

Stock photography

Excessive glassmorphism

Excessive gradient text

Template-looking cards

Overly rounded everything

Excessive animations

Cluttered dashboards

The website should feel like a premium developer infrastructure product.

Visual identity

Think:

Editorial developer tool × cinematic data visualization × modern AI SaaS

The visual language should combine:

Bold typography

Dark-first interface

Technical/data visualization

Interactive architecture graphs

Subtle 3D/depth effects

Precise motion

Minimal UI

High information density where appropriate

Generous whitespace

Strong visual hierarchy

The website should feel like a product that a serious engineering team would use.

3. DESIGN PRINCIPLE

The website itself should demonstrate the product.

Do not rely heavily on marketing copy.

Instead of telling users:

"ArchLens analyzes your codebase."

VISUALLY SHOW:

SOURCE CODE
     ↓
ANALYSIS
     ↓
DEPENDENCIES
     ↓
ARCHITECTURE


The architecture graph should be one of the main visual elements of the entire experience.

4. COLOR SYSTEM

Use a dark-first color system.

Base

Near-black / deep charcoal background.

Use subtle variations of dark surfaces instead of pure black everywhere.

Typography

Primary:

Off-white

Very light gray

Secondary:

Muted gray

Low-contrast gray

Accent

Use ONE distinctive accent color throughout the application.

The accent should be used for:

Active architecture nodes

Important edges

CTA buttons

Hover states

Selected components

AI-generated insights

Health indicators where appropriate

Do NOT use multiple bright accent colors everywhere.

The interface should remain sophisticated and restrained.

5. TYPOGRAPHY

Typography is a major design element.

Use a modern high-quality sans-serif font.

Use:

Extremely large display typography for the hero

Medium/large headings for sections

Compact technical typography for code/metadata

Monospace font for code snippets, file paths, API routes and technical labels

Hero typography should feel editorial and confident.

Example:

UNDERSTAND
YOUR CODEBASE.


Large enough to become a visual object.

6. NAVIGATION

Create a minimal floating navigation bar.

Desktop:

ARCHLENS

Product
How it works
Architecture
GitHub
Docs

[ Analyze Repository → ]


Requirements:

Transparent initially

Subtle dark surface after scrolling

Slight blur

Thin border

Smooth transition

Sticky navigation

Clean spacing

No unnecessary navigation items

Mobile navigation should collapse elegantly into a clean menu.

7. HERO SECTION

This is the most important section.

Create a cinematic hero.

Main headline

UNDERSTAND
YOUR CODEBASE.


Supporting copy:

ArchLens transforms source code into an intelligent,
visual map of your software architecture.


Primary CTA:

Analyze Repository →


Secondary CTA:

Explore Demo


8. HERO VISUAL

Do NOT use a generic 3D object.

Instead, create a live architecture graph.

The hero should contain a beautiful abstract architecture network.

Example:

              ┌─────────────┐
              │   FRONTEND  │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │ API SERVICE │
              └──────┬──────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
      ┌────────┐ ┌────────┐ ┌────────┐
      │  AUTH  │ │ USERS  │ │   ML   │
      └────────┘ └────────┘ └────┬───┘
                                  │
                                  ▼
                           ┌────────────┐
                           │  DATABASE  │
                           └────────────┘


But make it visually sophisticated rather than a basic flowchart.

Hero graph behavior

Nodes gently float

Edges subtly animate

Connections occasionally illuminate

Hovering a node highlights its connected nodes

Hovering an edge highlights the relationship

Mouse movement creates extremely subtle depth/parallax

Use smooth spring animations

Avoid distracting constant motion

The graph should feel alive but professional.

9. HERO MICRO-INTERACTION

When the user hovers over a node:

Display a small technical tooltip:

Prediction Service

Type
Service

Dependencies
14

Consumers
3

Confidence
94%


Connected nodes should subtly illuminate.

The purpose is to make the hero itself feel like a tiny demo of ArchLens.

10. HERO BACKGROUND

Use subtle visual texture.

Possible elements:

Fine grid

Extremely subtle noise

Very faint technical lines

Small data points

Architecture connections

Keep these extremely subtle.

Do NOT create a distracting cyberpunk background.

11. HERO SCROLL EXPERIENCE

As the user scrolls:

Hero typography moves upward slightly.

Architecture graph becomes more prominent.

The graph zooms in.

Individual components become visible.

Transition into the next section.

The transition should communicate:

CODE
   ↓
STRUCTURE
   ↓
ARCHITECTURE


12. SECTION — FROM CODE TO ARCHITECTURE

Create a large editorial section.

Headline:

FROM SOURCE CODE
TO SYSTEM MAP.


Supporting text:

ArchLens combines deterministic code analysis with AI-assisted
reasoning to reconstruct how your software actually works.


Then create a visual pipeline:

Repository
     ↓
AST Analysis
     ↓
Dependency Graph
     ↓
Architecture Inference
     ↓
AI Understanding


Animate each stage as the user scrolls.

13. SECTION — REPOSITORY ANALYSIS

Create a visual fake analysis console.

Show:

ANALYZING REPOSITORY

my-project/

✓ Scanning files
✓ Parsing Python modules
✓ Detecting imports
✓ Finding API routes
✓ Building dependency graph
✓ Detecting architecture

1,284 files scanned
43 modules detected
18 API routes
7 external services
2 circular dependencies


The numbers should animate naturally.

Use a technical monospace style.

This section should feel like a real developer tool rather than a marketing card.

14. SECTION — ARCHITECTURE VISUALIZATION

This should be one of the largest sections.

Headline:

SEE THE SYSTEM.
NOT JUST THE FILES.


Show a large interactive architecture graph.

Use realistic sample data.

Example:

React App
      ↓
API Gateway
      ↓
FastAPI
   ↙     ↘
Auth     Prediction
          ↓
       ML Model
          ↓
      PostgreSQL


The graph should support:

Zoom

Pan

Node selection

Hover

Highlighting

Smooth transitions

Since the backend is not connected yet, use mock/static data.

IMPORTANT:

Design the graph component so it can later consume backend JSON.

Do not hardcode the visualization architecture in a way that prevents API integration.

15. NODE INSPECTION PANEL

When a node is selected, show a side panel.

Example:

Prediction Service

SERVICE

Purpose
Handles model inference and prediction requests.

Dependencies

• model.py
• preprocessing.py
• database.py

API Consumers

• POST /predict
• POST /batch-predict

Confidence
94%

Source

services/prediction.py
Lines 21–184


Use technical typography.

Include:

View Source →


as a future-compatible action.

16. SECTION — AI EXPLANATION

Headline:

AI THAT EXPLAINS
THE ARCHITECTURE.


Show a split layout.

Left:

Architecture graph.

Right:

AI explanation panel.

Example:

WHY IS THIS A SERVICE?

ArchLens identified Prediction Service
as a service-layer component based on:

→ Imported by 3 API routes
→ Contains model inference logic
→ Depends on preprocessing
→ Called by prediction endpoints

Confidence

94%


Make it clear that AI reasoning is grounded in actual code evidence.

17. SECTION — ARCHITECTURE HEALTH

Headline:

KNOW WHEN
ARCHITECTURE BREAKS.


Create a premium architecture health visualization.

Example:

ARCHITECTURE HEALTH

82
/100

GOOD


Then:

✓ Clear API boundaries
✓ Low dependency depth
✓ Modular service layer

⚠ Circular dependency
⚠ High coupling in auth/


Add small metric visualizations for:

Coupling

Dependency depth

Complexity

Circular dependencies

Keep the design sophisticated.

Do not make it look like a generic analytics dashboard.

18. SECTION — ARCHITECTURE DIFF

Headline:

SEE HOW YOUR
ARCHITECTURE EVOLVES.


Create a before/after architecture visualization.

LEFT:

VERSION A

Frontend
   ↓
API
   ↓
PostgreSQL


RIGHT:

VERSION B

Frontend
   ↓
API
   ↓
Redis
   ↓
PostgreSQL


Animate the difference.

Show:

+ Redis Cache
+ Recommendation Service

~ API Service modified

- Legacy Auth


This should feel like Git diff meets architecture visualization.

19. SECTION — SUPPORTED TECHNOLOGIES

Eventually ArchLens should support multiple ecosystems.

Create a restrained technology section:

Python
FastAPI
Flask
React
Next.js
Node.js
TypeScript
PostgreSQL
Redis
Docker


Do not make this a giant logo wall.

Use clean typography and subtle icons.

20. FINAL CTA

Create a dramatic closing section.

Headline:

YOUR CODEBASE
ALREADY HAS A MAP.

YOU JUST CAN'T SEE IT YET.


CTA:

Analyze Your Repository →


Secondary:

View on GitHub


Use the architecture graph subtly in the background.

21. FOOTER

Minimal footer:

ARCHLENS

Understand your codebase.

Product
Architecture
GitHub
Docs
Privacy
Terms

© 2026 ArchLens AI


Keep it simple.

22. RESPONSIVE DESIGN

The website must work beautifully on:

Desktop

Laptop

Tablet

Mobile

Desktop should have the richest architecture visualization.

On mobile:

Simplify the graph

Allow horizontal scrolling or controlled zoom

Avoid tiny unreadable nodes

Stack split sections vertically

Preserve the visual hierarchy

Keep CTA accessible

Do NOT simply shrink the desktop layout.

Design mobile intentionally.

23. MOTION SYSTEM

Use motion carefully.

Preferred behavior:

Fade + slide

Scale transitions

Spring-based node movement

Scroll-triggered reveals

Graph highlighting

Smooth hover states

Subtle parallax

Section transitions

Avoid:

Excessive bouncing

Constant spinning objects

Huge cursor effects

Distracting particles

Long loading animations

Animations that interfere with usability

Motion should communicate relationships and structure.

24. ACCESSIBILITY

Implement:

Keyboard navigation

Visible focus states

Proper semantic HTML

Accessible buttons

ARIA labels where necessary

Sufficient contrast

Reduced-motion support

Respect:

prefers-reduced-motion


When reduced motion is enabled, simplify animations.

25. FRONTEND TECHNOLOGY

Use:

React

TypeScript

Tailwind CSS

React Flow

Modern component architecture

Use reusable components.

Avoid putting the entire website inside one huge component.

Suggested structure:

src/
├── components/
│   ├── Navbar/
│   ├── Hero/
│   ├── ArchitectureGraph/
│   ├── AnalysisConsole/
│   ├── NodeInspector/
│   ├── AIExplanation/
│   ├── HealthDashboard/
│   ├── ArchitectureDiff/
│   ├── CTA/
│   └── Footer/
│
├── pages/
│   ├── Home/
│   ├── Analyze/
│   └── Architecture/
│
├── data/
│   └── mockArchitecture.ts
│
├── types/
│   └── architecture.ts
│
├── hooks/
│
├── lib/
│
└── App.tsx


26. MOCK DATA

The backend is NOT connected yet.

Therefore create realistic mock data.

Create TypeScript interfaces such as:

interface ArchitectureNode {
  id: string;
  type: string;
  label: string;
  description?: string;
  confidence?: number;
  metadata?: Record<string, unknown>;
}

interface ArchitectureEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  confidence?: number;
}


Keep mock data separate from UI components.

Later we should be able to replace:

mockArchitecture.ts


with API responses without redesigning the frontend.

27. ANALYZE REPOSITORY EXPERIENCE

The main CTA should eventually lead to an analysis page.

For now create the complete frontend experience using mock processing.

Flow:

Analyze Repository
        ↓
Upload ZIP / Enter GitHub URL
        ↓
Analysis Progress
        ↓
Architecture Result


Create a polished repository input page.

Example:

┌───────────────────────────────────────┐
│                                       │
│       Analyze your repository        │
│                                       │
│  Drop a ZIP file here                 │
│             or                        │
│  Paste a GitHub repository URL        │
│                                       │
│       [ Analyze Repository ]          │
│                                       │
└───────────────────────────────────────┘


For now, this should use mock processing.

28. ANALYSIS PROGRESS EXPERIENCE

Create a visually polished analysis state.

Example:

ANALYZING REPOSITORY

✓ Repository loaded
✓ Scanning files
✓ Parsing source code
✓ Building dependency graph
● Inferring architecture
○ Calculating architecture health


Include a subtle architecture graph that progressively builds itself.

Do not use a generic spinner.

The progress visualization itself should communicate what ArchLens is doing.

29. RESULT DASHBOARD

Create a future-ready analysis result page.

Layout:

Repository
my-project

1,284 files
43 modules
18 API routes
7 external services

────────────────────────────

Architecture Graph

────────────────────────────

Architecture Health

82 / 100

────────────────────────────

AI Summary


The architecture graph should be the dominant visual element.

30. VISUAL QUALITY BAR

The final result should feel comparable to a high-end modern developer SaaS website.

Aim for:

Premium

Minimal

Technical

Cinematic

Precise

Intelligent

Confident

Avoid:

Template-looking SaaS

Overly colorful dashboards

Excessive cards

Excessive rounded corners

Generic AI aesthetics

Cheap gradients

Stock illustrations

31. IMPORTANT PRODUCT PHILOSOPHY

ArchLens is not:

"Another AI chatbot for developers."

It is:

A visual intelligence layer for software architecture.

The interface should communicate:

CODE
 ↓
STRUCTURE
 ↓
DEPENDENCIES
 ↓
ARCHITECTURE
 ↓
UNDERSTANDING


The architecture graph is the visual identity of the product.

32. PERFORMANCE

Optimize for:

Fast initial load

Lazy loading where appropriate

Efficient graph rendering

Avoid unnecessary re-renders

Avoid expensive animation loops

Responsive interactions

Do not sacrifice performance for visual effects.

33. CODE QUALITY

Use:

TypeScript strictly

Reusable components

Clear interfaces

Modular files

No unnecessary duplication

Clean naming

Maintainable styling

Do not create a giant single-page component.

34. FUTURE BACKEND INTEGRATION

The backend will eventually provide:

analysis.json
graph.json
architecture.json
health.json
diff.json


Design frontend data models around these concepts.

The frontend must not assume that mock data is permanent.

Keep API integration isolated in a service layer such as:

src/services/api.ts


35. DO NOT BUILD YET

Do NOT implement:

Real GitHub authentication

Real repository cloning

Real backend API

Real LLM calls

Real AST analysis

Real architecture health calculations

Real database integration

Use mock data for these.

The objective of this phase is to build an exceptional frontend experience that is ready to connect to the backend later.

36. FINAL EXPECTATION

Build the complete frontend experience, not just a landing page.

It should include:

Premium landing page

Interactive hero architecture graph

Product workflow sections

Repository analysis page

Mock analysis progress

Architecture visualization

Node inspection

AI explanation interface

Architecture health dashboard

Architecture diff

Responsive design

Dark-first visual system

Smooth but restrained motion

Mock data architecture ready for backend integration

The final experience should make someone visiting the site immediately understand:

"This tool takes a codebase and turns it into something I can actually understand."

Build this as a polished, production-quality frontend rather than a prototype or generic SaaS template.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
