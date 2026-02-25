# nanofolks Business Model

**Version:** 1.0  
**Date:** 2026-02-16  
**Status:** Proposal  

## Executive Summary

nanofolks follows an **Open Core business model**: a fully-featured open-source CLI tool for technical users, and a polished proprietary desktop application with cloud services for everyone else.

**Core Philosophy:**
- **Open Source CLI:** Full functionality, self-hosted, for developers and power users
- **Proprietary GUI:** Managed service, plug-and-play, for normal users (our target market)
- **Shared Goal:** Democratize AI access through approachable multi-agent systems

---

## Market Segmentation

### 1. Technical Users (Open Source CLI)

**Profile:**
- Developers, engineers, technical enthusiasts
- Comfortable with terminals, configuration files, API keys
- Value control, privacy, customization
- Willing to self-host and manage infrastructure

**Needs:**
- Full access to all features
- Ability to modify and extend
- No vendor lock-in
- Local data storage
- Bring-your-own-model flexibility

**Value Proposition:**
"Full-featured AI crew platform that you control completely. Free forever, community-driven."

### 2. Normal Users (Proprietary GUI)

**Profile:**
- Small business owners, professionals, students, parents
- Don't know what an API key is
- Want immediate value without configuration
- Prefer subscriptions over per-token pricing
- Value convenience over customization

**Needs:**
- Download and go
- Simple pricing (not per-token)
- Works everywhere (desktop + web)
- No technical setup
- Reliable, managed service

**Value Proposition:**
"Your AI crew, ready to help. Just install and start chatting. One simple price, unlimited use."

---

## Product Architecture

### Open Source CLI (nanofolks-cli)

**Repository:** Public, GitHub  
**License:** MIT  
**Language:** Go (1.21+)  
**Target:** Technical users

**Why Go for CLI:**
- Consistent with GUI backend architecture
- Single binary distribution (no Python dependencies)
- Better performance for concurrent operations
- Easy cross-platform builds
- Shared code with GUI where applicable
- Modern, type-safe codebase

**Features:**
- ✅ Full 6-bot coordination system
- ✅ Room management and memory
- ✅ All tools and skills
- ✅ Local SQLite storage
- ✅ File operations
- ✅ Self-hosted gateway
- ✅ WebSocket/REST API
- ✅ Import/export functionality
- ✅ Team support

**Setup Required:**
```bash
# Technical users handle this themselves
git clone https://github.com/nanofolks/nanofolks-cli
cd nanofolks-cli
go build
./nanofolks-cli onboard  # Configure API keys manually
```

**Monetization:** None (open source)

---

### Proprietary Desktop App (nanofolks-pro)

**Repository:** Private  
**License:** Commercial  
**Stack:** Go backend + Svelte 5 frontend (Wails v2)  
**Target:** Normal users

**Why Separate from CLI:**
- Different user experience requirements
- Cloud infrastructure integration
- Managed service model
- Polished UI/UX focus
- Team collaboration features

**Features:**
- ✅ Everything in CLI +
- ✅ Zero-configuration setup
- ✅ Managed model routing
- ✅ Cloud sync and backup
- ✅ Web access portal
- ✅ Automatic updates
- ✅ Priority support
- ✅ Team workspaces
- ✅ Mobile-responsive web version

**Setup Required:**
```bash
# Normal users do this
1. Download from nanofolks.ai
2. Install app
3. Create account
4. Start chatting
```

**Monetization:** Subscription-based

---

## Technical Architecture Comparison

```
┌─────────────────────────────────────────────────────────────┐
│                    OPEN SOURCE CLI                          │
│  (Go, MIT License, Self-Hosted)                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Go Binary (Single executable)                       │  │
│  │  ├─ Agent Loop (6 bots)                              │  │
│  │  ├─ Memory System (SQLite)                           │  │
│  │  ├─ Gateway Server (Optional)                        │  │
│  │  ├─ CLI Interface                                    │  │
│  │  └─ Config Management                                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  User manages:                                              │
│  • API keys for AI providers                               │
│  • Local database                                           │
│  • Configuration files                                      │
│  • Optional self-hosting setup                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              vs
┌─────────────────────────────────────────────────────────────┐
│                  PROPRIETARY DESKTOP APP                    │
│       (Go + Svelte, Commercial, Managed Service)            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Desktop App (Wails v2)                              │  │
│  │  ├─ Go Backend (Agent, Memory, Sync)                 │  │
│  │  └─ Svelte 5 Frontend (UI)                           │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                 │
│                           ▼ WebSocket/REST                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  nanofolks Cloud Backend                             │  │
│  │  ├─ User Management                                  │  │
│  │  ├─ Model Routing & Billing                          │  │
│  │  ├─ Sync & Backup                                    │  │
│  │  ├─ Web Access Portal                                │  │
│  │  └─ Analytics (opt-in)                               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  We manage:                                                 │
│  • AI provider relationships                               │
│  • Model routing optimization                             │
│  • User authentication                                     │
│  • Data sync and backup                                    │
│  • Infrastructure                                          │
│                                                             │
│  User just:                                                 │
│  • Creates account                                         │
│  • Pays subscription                                       │
│  • Uses the app                                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Why This Split Works

### 1. Different User Bases, Minimal Overlap

**Technical User (CLI):**
- "I want to self-host and control everything"
- "I have my own API keys"
- "I don't mind configuring things"
- **Not willing to pay for convenience**

**Normal User (GUI):**
- "I just want it to work"
- "What's an API key?"
- "Setup should take 2 minutes"
- **Willing to pay for convenience**

These are **different markets**. Mom won't self-host. Developers won't pay for managed models.

### 2. Marketing Synergy

**CLI generates awareness:**
- GitHub stars and community
- Developer word-of-mouth
- Technical credibility
- "Built by developers, for everyone"

**GUI captures revenue:**
- Converts non-technical users
- Managed service margins
- Recurring subscriptions
- Scales to mass market

### 3. Risk Mitigation

**If someone forks CLI and builds GUI:**
- They need to maintain it
- They need infrastructure
- They need to compete on polish
- Mom still won't use it (too technical)

**Reality:** OSS clones serve technical users, not our target market.

### 4. Community Benefits

- CLI contributors get recognition
- Bug fixes come from community
- Feature requests inform GUI roadmap
- Goodwill from OSS community
- Talent pipeline for hiring

---

## Pricing Strategy

### CLI (Open Source)

**Price:** Free (MIT License)  
**Revenue:** $0  
**Value:** Marketing, community, credibility

### GUI (Proprietary)

#### Consumer Plans

**Free Tier:**
- 1 bot (not full crew)
- 50 messages/day
- Local storage only
- Basic features
- **Goal:** Try before buy, viral spread

**Pro ($12/month):**
- Full 6-bot crew
- Unlimited messages
- Cloud sync
- Web access
- Priority support
- **Target:** Individual professionals

**Family ($20/month):**
- 3 user accounts
- Shared bots
- Individual workspaces
- **Target:** Households, small families

#### Business Plans

**Team ($25/user/month):**
- Everything in Pro +
- Shared workspaces
- Admin controls
- Usage analytics
- Custom bots
- **Target:** Small businesses, startups

**Enterprise (Custom):**
- SSO integration
- On-premise option
- Dedicated support
- SLA guarantees
- Custom development
- **Target:** Larger organizations

### Cost Structure (GUI)

**Our costs per Pro user:**
- Model API costs: ~$3-5/month
- Infrastructure: ~$1-2/month
- **Total:** ~$4-7/month

**Revenue per Pro user:** $12/month  
**Gross margin:** ~40-65%

At 1,000 users: $7,000-9,000/month profit  
At 10,000 users: $70,000-90,000/month profit

---

## Go vs Python for CLI

### Why Go (Recommended)

**Advantages:**
- ✅ Single binary (no Python installation)
- ✅ Better performance (concurrency)
- ✅ Type safety (fewer runtime errors)
- ✅ Easy cross-compilation
- ✅ Smaller distribution size
- ✅ Matches GUI backend (code sharing)
- ✅ Modern systems language
- ✅ Better for long-running processes

**Disadvantages:**
- Slower development than Python
- Smaller ecosystem for some tasks
- Steeper learning curve for contributors

### Why Not Python

**Issues:**
- Requires Python runtime (users need Python installed)
- Dependency management complexity (pip, venv)
- Slower execution
- Packaging difficulties (PyInstaller, etc.)
- Different from GUI stack
- Performance limitations

### Recommendation: **Go**

**Rationale:**
1. **Consistency:** Same language as GUI backend
2. **Distribution:** Single binary is huge for CLI adoption
3. **Performance:** Better for concurrent bot operations
4. **Professional:** Signals serious, modern project
5. **Future-proof:** Easier to maintain long-term

**Implementation:**
```go
// CLI entry point
cmd/nanofolks-cli/main.go

// Shared packages (can be extracted)
internal/agent/
internal/memory/
internal/gateway/

// CLI-specific
cmd/nanofolks-cli/commands/
cmd/nanofolks-cli/interactive/
```

---

## Repository Structure

### Public Repository (CLI)

```
nanofolks/nanofolks-cli (GitHub - Public)
├── LICENSE (MIT)
├── README.md
├── Makefile
├── go.mod
│
├── cmd/
│   └── nanofolks-cli/
│       └── main.go              # CLI entry point
│
├── internal/
│   ├── agent/                   # 6-bot coordination
│   ├── memory/                  # SQLite operations
│   ├── gateway/                 # WebSocket/REST server
│   ├── skills/                  # Skill system
│   └── config/                  # Configuration
│
├── pkg/
│   └── utils/                   # Shared utilities
│
└── docs/
    └── cli-usage.md
```

### Private Repository (GUI + Cloud)

```
nanofolks/nanofolks-pro (Private)
├── LICENSE (Commercial)
├── README.md (internal)
│
├── backend/                     # Go backend
│   ├── cmd/
│   │   ├── desktop/             # Desktop app entry
│   │   └── cloud/               # Cloud service entry
│   ├── internal/
│   │   ├── cloud/               # Cloud-specific logic
│   │   ├── billing/             # Subscription management
│   │   ├── sync/                # Data synchronization
│   │   └── ... (shared with CLI)
│   └── pkg/
│
├── frontend/                    # Svelte 5 + Wails
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/
│   │   │   ├── stores/
│   │   │   └── ...
│   │   └── routes/
│   └── static/
│
├── cloud/                       # Cloud infrastructure
│   ├── terraform/               # Infrastructure as code
│   ├── kubernetes/              # K8s configs
│   └── scripts/
│
└── docs/
    └── architecture.md
```

### Shared Components

**Option A: Monorepo with Private Modules**
```
nanofolks/nanofolks-core (Public)
├── go.mod
├── internal/                    # Shared logic
│   ├── agent/
│   ├── memory/
│   └── types/
└── LICENSE (MIT)
```

**Option B: Git Submodules**
- CLI includes core as submodule
- GUI includes core as submodule

**Option C: Copy/Paste (Pragmatic)**
- Accept some code duplication
- CLI and GUI evolve independently
- Lower coupling, higher autonomy

**Recommendation:** Option A (Shared core library)

---

## Go-to-Market Strategy

### Phase 1: Build CLI (Months 1-3)

**Goals:**
- Full-featured CLI in Go
- Complete documentation
- Basic community
- 100 GitHub stars

**Activities:**
- Open source the CLI
- Post on Hacker News, Reddit
- Engage with AI/Go communities
- Gather feedback from technical users

### Phase 2: Build GUI (Months 4-6)

**Goals:**
- Polished desktop app
- Cloud backend
- Beta testing with CLI community
- 100 beta users

**Activities:**
- Private beta for CLI contributors
- Iterate on UX
- Build cloud infrastructure
- Set up billing/subscriptions

### Phase 3: Launch (Month 7)

**Goals:**
- Public launch of GUI
- First 100 paying customers
- Media coverage
- Strong positioning

**Activities:**
- Product Hunt launch
- Tech press outreach
- Content marketing (blog, tutorials)
- Referral program

### Phase 4: Scale (Months 8-12)

**Goals:**
- 1,000 paying customers
- Team/Enterprise plans
- Strategic partnerships
- $10k+ MRR

**Activities:**
- Enterprise outreach
- Integration partnerships
- Advanced features (voice, mobile)
- Community events

---

## Competitive Moat

### Why GUI Users Won't Switch to CLI

**Friction:**
- Need to understand API keys
- Need to configure providers
- Need to manage infrastructure
- No cloud sync
- No web access
- No automatic updates
- No support

**Mom Test:**
"Hey mom, you can pay $12/month for the easy version, or spend 3 hours setting up the free version. Which do you want?"

### Why CLI Users Might Upgrade to GUI

**Convenience:**
- "I'm traveling, want web access"
- "Don't want to manage API keys anymore"
- "Want it to just work"
- "Need sync between devices"

**Migration Path:**
- Import CLI data to GUI
- Special discount for OSS contributors
- Seamless transition

---

## Risk Analysis

### Risk 1: CLI Becomes Too Popular

**Scenario:** Everyone uses free CLI, no one pays

**Mitigation:**
- CLI requires technical setup (natural filter)
- GUI has clear convenience advantages
- Different target markets
- OSS goodwill attracts enterprise customers

### Risk 2: Someone Forks and Competes

**Scenario:** Fork creates better GUI

**Mitigation:**
- Need infrastructure to compete (hard)
- Mom won't use fork (too technical)
- We control the brand and community
- First-mover advantage

### Risk 3: Maintenance Burden

**Scenario:** Two products = 2x work

**Mitigation:**
- Shared core library
- CLI community contributes
- GUI is priority for revenue
- CLI gets fewer updates (acceptable)

### Risk 4: Cloud Costs

**Scenario:** Model costs exceed revenue

**Mitigation:**
- Smart routing (cheaper models when possible)
- Usage limits on lower tiers
- Efficient prompt engineering
- Markup protects margins

---

## Success Metrics

### CLI (Open Source)

- GitHub stars: 1,000 (Year 1), 5,000 (Year 2)
- Active contributors: 10+ 
- Community satisfaction: High
- Technical credibility: Established

### GUI (Commercial)

- Free tier users: 10,000 (Year 1)
- Paying customers: 500 (Year 1), 5,000 (Year 2)
- MRR: $6,000 (Year 1), $60,000 (Year 2)
- Churn: <5% monthly
- NPS: >50

---

## Conclusion

The Open Core model with Go CLI and proprietary GUI is the optimal strategy for nanofolks:

1. **Technical users** get full control (CLI)
2. **Normal users** get convenience (GUI)
3. **Markets don't overlap** (different user bases)
4. **OSS drives awareness** (free marketing)
5. **GUI captures value** (subscription revenue)
6. **Go for both** ensures consistency and performance

**Key Insight:** We're not selling software. We're selling **convenience and peace of mind** to people who want AI help without technical complexity.

The CLI builds credibility and community. The GUI monetizes the mass market that wants "just install and go."

---

## Next Steps

1. **Set up repositories:**
   - Create `nanofolks-cli` (public, Go, MIT)
   - Create `nanofolks-pro` (private, Go+Svelte, Commercial)
   - Create `nanofolks-core` (public, Go, MIT - shared library)

2. **Build CLI first:**
   - Port Python functionality to Go
   - Ensure feature parity
   - Document thoroughly
   - Build community

3. **Then build GUI:**
   - Use shared core
   - Add cloud infrastructure
   - Polish UX for non-technical users
   - Implement billing

4. **Launch strategy:**
   - CLI: Open source immediately
   - GUI: Private beta, then public launch
   - Marketing: "Built by developers, for everyone"

---

**Authors:** nanofolks Team  
**Status:** Proposal - Ready for Implementation
