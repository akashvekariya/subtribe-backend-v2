# AI Evaluation System Design

> **TLDR**: Complete AI candidate evaluation system design - two-tier evaluation (candidate assessment + job fit), Evaluation Template System (role-specific criteria), A-FIT scoring framework, async processing with Cloud Tasks, GPT-4/Claude powered. **Status: DEFERRED to V1.1**. Design complete, implementation pending. File preserved for V1.1 development. **For V1**: Skip this entirely, focus on core ATS features first.

---

## ⚠️ STATUS: V1.1 - DEFERRED

**Decision Date**: 2025-09-30  
**Reason**: AI evaluation is highly complex and requires dedicated focus. Deferring to v1.1 to prioritize other backend components first.

**Current State**: Design phase completed through Evaluation Template System (ETS) architecture. Ready to resume implementation when prioritized.

**Resume From**: Section 7 - "Cross-Stage Consistency" implementation and BAML prompt engineering.

---

## SNAPSHOT: Key Decisions Made

### Architecture Decisions
✅ **Two-tier evaluation**: Independent candidate assessment + candidate-job fit  
✅ **Evaluation Template System (ETS)**: Dynamic, role-specific evaluation criteria  
✅ **Storage**: Separate `evaluations` table with template snapshots for immutability  
✅ **Processing**: Async background tasks (Cloud Tasks) triggered on application submission  
✅ **Models**: Gemini 2.5 Flash Lite for parsing, GPT-4/Claude for evaluation  
✅ **Framework**: A-FIT (Alignment, Forte, Impact, Trajectory) with template-customizable weights  

### V1 Scope Boundaries
✅ Automatic evaluation on submission (no manual trigger)  
✅ Single evaluation per application (no re-evaluation)  
✅ Staleness marking when job description changes (no auto re-trigger)  
✅ System-default templates only (no company-custom templates)  
✅ 2-retry policy with "Evaluation Pending" fallback  
✅ Duplicate prevention: one email per job (unique constraint)  

### Open Questions (Revisit in v1.1)
- Skills taxonomy vs LLM semantic matching trade-off
- Bias mitigation strategy (PII stripping, audit process)
- Final template list (10-15 role types for launch)
- Resume parsing quality threshold definition
- Cost optimization targets ($0.05 vs $0.10 per evaluation)

---

## EVALUATION TEMPLATE SYSTEM (ETS) - DETAILED ARCHITECTURE

### ETS Overview

**Core Concept**: Reusable evaluation configurations that define how different role types should be assessed.

**Benefits**:
1. **Scalability**: Engineering ≠ Sales ≠ Legal roles get appropriate evaluation criteria
2. **Consistency**: All "Backend Engineer" jobs use same evaluation framework
3. **Extensibility**: Add new templates without code changes
4. **Multi-stage Ready**: Same template can inform screening calls, technical tests, interviews (future)
5. **Client Customization**: Foundation for company-specific templates (V2+)

---

### ETS Database Schema

#### New Table: `evaluation_templates`

```sql
CREATE TABLE evaluation_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id),  -- NULL = system default, non-NULL = company custom
    
    -- Template Identity
    name VARCHAR(255) NOT NULL,  -- "Software Engineer", "Sales Manager", "Legal Counsel"
    slug VARCHAR(100) NOT NULL,  -- "software-engineer", "sales-manager"
    description TEXT,
    category VARCHAR(100),  -- "engineering", "sales", "legal", "medical", "creative"
    
    -- Evaluation Configuration (JSONB for flexibility)
    dimensions JSONB NOT NULL,  -- Dimension definitions + weights
    skill_matching_rules JSONB,  -- How to evaluate skills for this role type
    output_preferences JSONB,  -- What to emphasize in summary
    
    -- Versioning
    version INTEGER DEFAULT 1,
    parent_template_id UUID REFERENCES evaluation_templates(id),  -- For template evolution
    
    -- Metadata
    is_active BOOLEAN DEFAULT true,
    is_system_default BOOLEAN DEFAULT false,  -- Provided by platform vs custom
    usage_count INTEGER DEFAULT 0,  -- How many jobs use this template
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_company_slug UNIQUE (company_id, slug)
);

CREATE INDEX idx_evaluation_templates_company ON evaluation_templates(company_id);
CREATE INDEX idx_evaluation_templates_category ON evaluation_templates(category);
CREATE INDEX idx_evaluation_templates_system_default ON evaluation_templates(is_system_default);
CREATE INDEX idx_evaluation_templates_active ON evaluation_templates(is_active);
```

#### Update: `jobs` table

```sql
ALTER TABLE jobs ADD COLUMN evaluation_template_id UUID REFERENCES evaluation_templates(id);
CREATE INDEX idx_jobs_evaluation_template ON jobs(evaluation_template_id);
```

#### Update: `evaluations` table

```sql
-- Store template snapshot at evaluation time (immutability principle)
ALTER TABLE evaluations ADD COLUMN template_snapshot JSONB;
```

**Why template_snapshot?**
- Evaluations remain consistent even if template is updated later
- Audit trail: know exactly what criteria were used
- Enables template A/B testing without affecting existing evaluations

---

### Template Configuration Schema

#### Example 1: Backend Engineer Template

```json
{
  "template_id": "uuid-here",
  "name": "Software Engineer (Backend)",
  "slug": "backend-engineer",
  "category": "engineering",
  "description": "Evaluation criteria optimized for backend engineering roles focusing on technical depth, system design, and scalability.",
  
  "dimensions": {
    "alignment": {
      "weight": 0.40,
      "enabled": true,
      "description": "How well candidate's skills and experience match job requirements",
      "components": {
        "skills_match": {
          "weight": 0.70,
          "must_have_importance": 0.80,  // Must-haves are 80% of skills score
          "nice_to_have_importance": 0.20,
          "recency_multiplier": 1.2  // Boost score for recently-used skills
        },
        "experience_match": {
          "weight": 0.30,
          "min_years_required": true,  // Strict on years of experience
          "seniority_match_required": true,
          "allow_adjacent_levels": true  // Mid can apply for Senior with strong skills
        }
      }
    },
    
    "forte": {
      "weight": 0.30,
      "enabled": true,
      "description": "Depth and relevance of past work experience",
      "components": {
        "role_relevance": {
          "weight": 0.40,
          "focus": "technical_depth",  // vs "breadth" or "leadership"
          "semantic_matching": true  // Use LLM for semantic similarity
        },
        "responsibility_overlap": {
          "weight": 0.40,
          "semantic_threshold": 0.70,  // LLM similarity score threshold
          "prioritize_recent_roles": true
        },
        "domain_experience": {
          "weight": 0.20,
          "required": false,  // Industry experience is nice-to-have, not critical
          "bonus_for_match": 10  // +10 points if domain matches
        }
      }
    },
    
    "impact": {
      "weight": 0.20,
      "enabled": true,
      "description": "Proven ability to deliver measurable results",
      "components": {
        "quantifiable_achievements": {
          "weight": 0.60,
          "minimum_required": 1,  // Must have at least 1 quantified achievement
          "complexity_weight": 0.70,  // Technical complexity matters more than scale
          "look_for_patterns": [
            "performance_optimization",
            "scalability_improvements",
            "cost_reduction",
            "reliability_enhancements"
          ]
        },
        "innovation_indicators": {
          "weight": 0.40,
          "types": ["open_source", "patents", "publications", "conference_talks"],
          "bonus_points": {
            "open_source_maintainer": 15,
            "patent_holder": 20,
            "published_author": 15,
            "conference_speaker": 10
          }
        }
      }
    },
    
    "trajectory": {
      "weight": 0.10,
      "enabled": true,
      "description": "Career progression and stability indicators",
      "components": {
        "career_growth": {
          "weight": 0.50,
          "promotion_bonus": 15,  // +15 points for each promotion
          "title_progression_matters": true
        },
        "stability": {
          "weight": 0.30,
          "short_tenure_penalty": -10,  // -10 per stint <1 year
          "ideal_tenure_months": 24,  // 2 years is ideal
          "contract_roles_exempt": true  // Don't penalize contractors
        },
        "relevance_trend": {
          "weight": 0.20,
          "recent_experience_multiplier": 1.5  // Most recent role weighted 1.5x
        }
      }
    }
  },
  
  "skill_matching_rules": {
    "skill_categories": {
      "programming_languages": {
        "importance": "critical",
        "exact_match_required": false,  // Python experience transfers to similar languages
        "proficiency_matters": true,  // Years of experience with skill matters
        "recency_decay_months": 24,  // Skills >2 years old decay in value
        "related_skills_boost": true  // Java knowledge helps with Kotlin
      },
      "frameworks": {
        "importance": "high",
        "exact_match_required": true,  // FastAPI != Flask (more specific)
        "related_skills_count": true,  // Django experience helps with FastAPI
        "version_matters": false  // FastAPI 0.68 vs 0.95 doesn't matter much
      },
      "databases": {
        "importance": "high",
        "exact_match_required": false,  // PostgreSQL experience transfers to MySQL
        "category_match_sufficient": true,  // Any SQL database counts
        "nosql_vs_sql_distinction": true
      },
      "tools_and_platforms": {
        "importance": "medium",
        "exact_match_required": false,  // Docker != K8s but related
        "trainable": true,  // Easy to learn, not a blocker
        "cloud_provider_agnostic": true  // AWS ≈ GCP ≈ Azure experience
      },
      "soft_skills": {
        "importance": "low",
        "inferred_from_experience": true,  // Don't rely on self-reported soft skills
        "action_verb_analysis": true  // "Led", "Mentored" indicate leadership
      }
    }
  },
  
  "output_preferences": {
    "summary_focus": [
      "technical_depth",
      "problem_solving",
      "system_design_experience",
      "code_quality",
      "scalability_mindset"
    ],
    "highlight_priorities": [
      "scalability_achievements",
      "performance_optimization",
      "architecture_decisions",
      "mentorship_or_leadership",
      "open_source_contributions"
    ],
    "interview_question_types": [
      "system_design",
      "coding_problem_solving",
      "past_project_deep_dive",
      "scalability_challenges",
      "debugging_war_stories"
    ],
    "red_flags_to_surface": [
      "no_quantifiable_impact",
      "frequent_job_hopping",
      "outdated_tech_stack",
      "lack_of_ownership_language",
      "no_evidence_of_learning"
    ]
  }
}
```

#### Example 2: Sales Manager Template

```json
{
  "template_id": "uuid-here",
  "name": "Sales Manager",
  "slug": "sales-manager",
  "category": "sales",
  "description": "Evaluation criteria optimized for sales leadership roles focusing on quota attainment, deal velocity, and team management.",
  
  "dimensions": {
    "alignment": {
      "weight": 0.30,  // Lower weight - skills less critical than results in sales
      "enabled": true,
      "components": {
        "skills_match": {
          "weight": 0.50,
          "focus": "tools_and_platforms",  // CRM, sales tools
          "methodology_match": true  // MEDDIC, Challenger, etc.
        },
        "experience_match": {
          "weight": 0.50,
          "min_years_required": true,
          "deal_size_alignment": true  // SMB vs Mid-Market vs Enterprise
        }
      }
    },
    
    "forte": {
      "weight": 0.25,
      "enabled": true,
      "components": {
        "industry_experience": {
          "weight": 0.60,  // Industry knowledge critical for sales
          "required": true,
          "vertical_match_bonus": 20  // +20 if same vertical (e.g., SaaS, fintech)
        },
        "deal_size_match": {
          "weight": 0.40,
          "enterprise_vs_smb": true,  // Match deal size experience
          "acv_range_alignment": true  // $10K deals != $1M deals
        }
      }
    },
    
    "impact": {
      "weight": 0.35,  // HIGHEST weight - results are everything in sales
      "enabled": true,
      "components": {
        "quota_attainment": {
          "weight": 0.60,
          "minimum_required": 2,  // Must show 2+ instances of hitting quota
          "percentage_threshold": 100,  // 100%+ quota attainment
          "consistency_matters": true,  // Prefer consistent performance
          "president_club_bonus": 20  // +20 for top performer recognition
        },
        "revenue_impact": {
          "weight": 0.40,
          "quantifiable_required": true,  // "$2M ARR closed" etc.
          "growth_trajectory_matters": true,  // Year-over-year improvement
          "team_revenue_if_manager": true  // Include team's revenue for managers
        }
      }
    },
    
    "trajectory": {
      "weight": 0.10,
      "enabled": true,
      "components": {
        "promotion_velocity": {
          "weight": 0.60,  // Sales = meritocracy, promotions matter
          "promotion_bonus": 20,
          "individual_to_manager_path": true  // IC → Manager is strong signal
        },
        "stability": {
          "weight": 0.40,
          "short_tenure_penalty": -5,  // Less penalty than engineering
          "sales_turnover_context": true  // Sales has higher natural turnover
        }
      }
    }
  },
  
  "skill_matching_rules": {
    "skill_categories": {
      "sales_methodology": {
        "importance": "critical",
        "types": ["MEDDIC", "Challenger", "Solution Selling", "SPIN", "Sandler"],
        "must_have_one": true
      },
      "crm_platforms": {
        "importance": "medium",
        "trainable": true,
        "common_platforms": ["Salesforce", "HubSpot", "Pipedrive"]
      },
      "sales_tools": {
        "importance": "low",
        "examples": ["Outreach", "SalesLoft", "Gong", "Chorus"],
        "nice_to_have": true
      },
      "soft_skills": {
        "importance": "critical",  // Much higher than engineering
        "types": [
          "negotiation",
          "relationship_building",
          "executive_presence",
          "objection_handling",
          "active_listening"
        ],
        "inferred_from_achievements": true
      }
    }
  },
  
  "output_preferences": {
    "summary_focus": [
      "quota_attainment_history",
      "deal_velocity",
      "customer_relationships",
      "team_leadership",
      "pipeline_management"
    ],
    "highlight_priorities": [
      "record_breaking_performance",
      "awards_and_recognition",
      "key_account_wins",
      "team_development",
      "process_improvements"
    ],
    "interview_question_types": [
      "behavioral_selling_scenarios",
      "objection_handling",
      "deal_walkthrough",
      "quota_attainment_explanation",
      "customer_relationship_management"
    ],
    "red_flags_to_surface": [
      "no_quota_attainment_data",
      "declining_performance_trend",
      "short_tenures_without_explanation",
      "lack_of_team_leadership_for_manager_role"
    ]
  }
}
```

#### Example 3: Product Manager Template

```json
{
  "name": "Product Manager",
  "slug": "product-manager",
  "category": "product",
  
  "dimensions": {
    "alignment": {
      "weight": 0.35,
      "components": {
        "product_skills": {
          "weight": 0.60,
          "areas": ["roadmapping", "user_research", "data_analysis", "stakeholder_management"]
        },
        "domain_knowledge": {
          "weight": 0.40,
          "industry_match_critical": true,
          "b2b_vs_b2c_distinction": true
        }
      }
    },
    "forte": {
      "weight": 0.30,
      "components": {
        "product_lifecycle_experience": {
          "weight": 0.50,
          "stages": ["0_to_1", "growth", "maturity", "turnaround"]
        },
        "cross_functional_leadership": {
          "weight": 0.50,
          "evidence_required": true  // Led eng, design, marketing
        }
      }
    },
    "impact": {
      "weight": 0.30,  // Slightly higher for PM
      "components": {
        "product_outcomes": {
          "weight": 0.70,
          "metrics": ["user_growth", "revenue_impact", "engagement_lift", "churn_reduction"]
        },
        "strategic_initiatives": {
          "weight": 0.30,
          "new_product_launches": true,
          "market_expansion": true
        }
      }
    },
    "trajectory": {
      "weight": 0.05,  // Less important for PM
      "components": {
        "product_complexity_growth": {
          "weight": 1.0,
          "simple_to_complex_products": true
        }
      }
    }
  },
  
  "output_preferences": {
    "summary_focus": [
      "product_sense",
      "data_driven_decision_making",
      "stakeholder_management",
      "technical_fluency"
    ]
  }
}
```

---

### System Default Templates (V1)

Ship with 10-15 pre-built templates covering common roles:

#### Engineering (6 templates)
1. **Backend Engineer** - API design, databases, system architecture
2. **Frontend Engineer** - UI/UX implementation, performance optimization
3. **Full Stack Engineer** - Balanced frontend/backend evaluation
4. **DevOps/SRE Engineer** - Infrastructure, reliability, automation
5. **Data Engineer** - ETL, data pipelines, big data technologies
6. **Mobile Engineer** - iOS/Android development, app performance

#### Product & Design (3 templates)
7. **Product Manager** - Product strategy, user outcomes, cross-functional leadership
8. **UX/UI Designer** - Design portfolio, user research, visual design
9. **Product Designer** - End-to-end product design, prototyping

#### Sales & Marketing (4 templates)
10. **Sales Manager** - Quota attainment, team leadership, deal velocity
11. **Account Executive** - Individual quota, pipeline management, closing ability
12. **Marketing Manager** - Campaign performance, lead generation, brand building
13. **Customer Success Manager** - Retention, expansion, customer satisfaction

#### Operations (2 templates)
14. **Operations Manager** - Process optimization, cross-functional coordination
15. **Business Analyst** - Data analysis, requirements gathering, stakeholder management

**V1 Scope**: System defaults only (company-id = NULL)  
**V2 Scope**: Allow companies to create custom templates (company-id != NULL)

---

### Job Creation Flow with ETS

#### Recruiter Experience

```
Step 1: Basic Job Info
  - Title: "Senior Backend Engineer"
  - Description: (Markdown editor)
  - Department: Engineering
    ↓
Step 2: Select Evaluation Template ← NEW
  - Auto-suggested based on job title keywords
  - Dropdown: "Engineering" category
  - Template cards with preview:
    ┌─────────────────────────────────────────┐
    │ Backend Engineer                        │
    │ ─────────────────────────────────────── │
    │ Evaluates: Skills (40%), Experience     │
    │ (30%), Impact (20%), Career (10%)       │
    │                                         │
    │ Best for: API development, databases,   │
    │ system design roles                     │
    │                                         │
    │ [Preview Details] [Select Template] ←   │
    └─────────────────────────────────────────┘
    ↓
Step 3: Define Required Skills
  - Template provides suggestions: "Python, FastAPI, PostgreSQL, Docker, AWS"
  - Recruiter adds/removes/edits skills
  - Mark each as: Must-have ⭐ or Nice-to-have ✨
    ↓
Step 4: Job Details
  - Location, salary, experience level, etc.
    ↓
Step 5: Review & Publish
  - Shows: Job will be evaluated using "Backend Engineer" template
  - Preview evaluation criteria
    ↓
Job Created → evaluation_template_id stored
```

#### API Endpoint

```python
POST /api/v1/jobs

{
  "title": "Senior Backend Engineer",
  "description": "We're looking for...",
  "evaluation_template_id": "uuid-of-backend-engineer-template",
  
  "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
  "preferred_skills": ["Kubernetes", "Redis", "AWS", "Terraform"],
  
  "position_type": "full_time",
  "experience_level": "senior",
  "location_type": "remote",
  ...
}

Response:
{
  "id": "job-uuid",
  "slug": "senior-backend-engineer-abc123",
  "evaluation_template": {
    "id": "template-uuid",
    "name": "Backend Engineer",
    "dimensions_summary": {
      "alignment": 40,
      "forte": 30,
      "impact": 20,
      "trajectory": 10
    }
  },
  ...
}
```

---

### Evaluation Execution with ETS

#### When Application is Submitted

```python
async def evaluate_application(application_id: UUID):
    """
    Main evaluation orchestration function with ETS support
    """
    # 1. Fetch application, job, and evaluation template
    application = await db.get_application(application_id)
    job = await db.get_job(application.job_id)
    template = await db.get_evaluation_template(job.evaluation_template_id)
    
    # 2. Take immutable snapshot of template
    template_snapshot = template.to_dict()
    
    # 3. Parse resume
    parsed_resume = await parse_resume_with_gemini(
        resume_url=application.resume_url
    )
    
    # Store parsed text
    await db.update_application(
        application_id,
        resume_parsed_text=parsed_resume.full_text,
        resume_metadata={
            "extraction_method": "gemini-2.5-flash-lite",
            "extracted_at": datetime.utcnow(),
            "links_extracted": parsed_resume.links,
            "extraction_confidence": parsed_resume.confidence
        }
    )
    
    # 4. Run evaluation with template-driven configuration
    evaluation_result = await baml_client.JobFitEvaluator(
        # Input data
        resume_text=parsed_resume.full_text,
        resume_structured=parsed_resume.structured_data,
        job_description=job.description,
        required_skills=job.required_skills,
        preferred_skills=job.preferred_skills,
        experience_level=job.experience_level,
        
        # Template configuration (dynamic!)
        evaluation_config={
            "dimensions": template.dimensions,
            "skill_matching_rules": template.skill_matching_rules,
            "output_preferences": template.output_preferences
        }
    )
    
    # 5. Calculate weighted overall score using template weights
    dimensions = template.dimensions
    overall_score = (
        evaluation_result.alignment_score * dimensions["alignment"]["weight"] +
        evaluation_result.forte_score * dimensions["forte"]["weight"] +
        evaluation_result.impact_score * dimensions["impact"]["weight"] +
        evaluation_result.trajectory_score * dimensions["trajectory"]["weight"]
    )
    
    # Determine score tier
    score_tier = get_score_tier(overall_score)
    
    # 6. Store evaluation with template snapshot
    evaluation = await db.create_evaluation(
        application_id=application_id,
        job_id=job.id,
        company_id=job.company_id,
        evaluation_type="job_fit",
        
        # Scores
        overall_score=overall_score,
        score_tier=score_tier,
        alignment_score=evaluation_result.alignment_score,
        forte_score=evaluation_result.forte_score,
        impact_score=evaluation_result.impact_score,
        trajectory_score=evaluation_result.trajectory_score,
        
        # Detailed breakdown
        skills_breakdown=evaluation_result.skills_breakdown,
        strengths=evaluation_result.strengths,
        gaps=evaluation_result.gaps,
        highlights=evaluation_result.highlights,
        summary=evaluation_result.summary,
        recommended_questions=evaluation_result.interview_questions,
        
        # Template tracking (immutability)
        template_snapshot=template_snapshot,
        
        # Model metadata
        model_name=EVALUATOR_MODEL,
        model_version=PROMPT_VERSION,
        prompt_hash=hash_prompt(EVALUATION_PROMPT),
        
        # Cost tracking
        tokens_used=evaluation_result.token_usage,
        estimated_cost_usd=calculate_cost(evaluation_result.token_usage),
        
        # Performance
        latency_ms=evaluation_result.latency_ms,
        
        status="completed",
        evaluated_at=datetime.utcnow()
    )
    
    # 7. Update application with evaluation summary (denormalized for fast access)
    await db.update_application(
        application_id,
        evaluation_status="completed",
        evaluation_summary={
            "overall_score": overall_score,
            "score_tier": score_tier,
            "top_strengths": evaluation_result.strengths[:3],
            "top_gaps": evaluation_result.gaps[:2],
            "evaluated_at": datetime.utcnow().isoformat()
        }
    )
    
    return evaluation


def get_score_tier(score: float) -> str:
    """Map numerical score to tier label"""
    if score >= 90:
        return "top_tier"
    elif score >= 75:
        return "strong_fit"
    elif score >= 60:
        return "potential_fit"
    else:
        return "not_fit"
```

---

### Template Versioning & Evolution

**Challenge**: What happens when we improve a template (e.g., adjust weights)?

**Solution**: Template Versioning with Immutable Snapshots

#### Strategy

1. **Template Updates Create New Versions**
   - Don't modify existing template in-place
   - Create new version, link to parent via `parent_template_id`
   - Increment `version` field

2. **Existing Jobs Continue Using Old Version**
   - Jobs store `evaluation_template_id` - reference doesn't change
   - Provides stability - evaluations remain consistent

3. **New Jobs Use Latest Version**
   - Job creation API fetches latest active version of template
   - Recruiter can optionally choose older version if preferred

4. **Evaluations Store Snapshot**
   - `evaluations.template_snapshot` JSONB contains full template config
   - Even if template is deleted, evaluation remains valid
   - Audit trail: know exactly what criteria were used

#### Example Workflow

```python
# Template evolution over time
v1 = EvaluationTemplate(
    name="Backend Engineer",
    slug="backend-engineer",
    version=1,
    dimensions={"alignment": {"weight": 0.40}, ...}
)

# Later: We want to adjust weights
v2 = EvaluationTemplate(
    name="Backend Engineer",
    slug="backend-engineer",
    version=2,
    parent_template_id=v1.id,  # Link to previous version
    dimensions={"alignment": {"weight": 0.45}, ...}  # Adjusted
)

# Mark v1 as superseded (optional)
v1.is_active = False
v2.is_active = True

# Jobs created before change: Still reference v1
# Jobs created after change: Reference v2
# Evaluations: Always store snapshot, unaffected by changes
```

---

### Cross-Stage Consistency (Future Vision)

**Long-term Goal**: Use same template across entire hiring pipeline

```
┌─────────────────────────────────────────────────────────────┐
│ Evaluation Template: "Backend Engineer"                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Stage 1: Resume Screening                                   │
│   - Dimensions: Alignment, Forte, Impact, Trajectory        │
│   - Pass Threshold: 60                                      │
│   - Output: Ranked candidate list                           │
│                                                             │
│ Stage 2: Phone Screen (V2)                                  │
│   - Focus Areas: Technical depth, Communication             │
│   - Questions: Auto-generated from resume gaps              │
│   - Pass Threshold: 70                                      │
│                                                             │
│ Stage 3: Technical Interview (V2)                           │
│   - Focus Areas: Coding, System Design, Debugging           │
│   - Difficulty: Calibrated to resume score                  │
│   - Pass Threshold: 75                                      │
│                                                             │
│ Stage 4: Final Interview (V2)                               │
│   - Focus Areas: Culture fit, Leadership, Motivation        │
│   - Pass Threshold: 80                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Benefits**:
- Consistent evaluation criteria across all stages
- Interview questions derived from resume evaluation gaps
- Difficulty calibration based on candidate strength
- Holistic candidate profile built incrementally

**V1 Scope**: Resume evaluation only  
**V2+ Scope**: Expand to phone screens, technical tests, interviews

---

### Key Architectural Decisions

#### 1. Template Customization in V1?

**Decision**: System-default templates only (V1)

**Rationale**:
- Faster to ship - no UI for template editing
- Validate template structure with real usage first
- 10-15 pre-built templates cover 80% of use cases
- Reduces complexity for pilot clients

**V2**: Add company-custom templates with visual editor

---

#### 2. Template Selection: Required or Optional?

**Decision**: Required with smart auto-suggestion

**Rationale**:
- Enforces consistency across all jobs
- Ensures every evaluation is properly configured
- Auto-suggestion reduces friction (detects "Backend Engineer" in title → suggests template)
- Fallback: "Generic" template if no good match

**Implementation**:
```python
def suggest_template(job_title: str) -> List[EvaluationTemplate]:
    """Auto-suggest templates based on job title keywords"""
    title_lower = job_title.lower()
    
    # Keyword mapping
    if any(kw in title_lower for kw in ["backend", "api", "server"]):
        return get_templates(category="engineering", slug="backend-engineer")
    elif "frontend" in title_lower or "react" in title_lower:
        return get_templates(slug="frontend-engineer")
    elif "sales" in title_lower:
        return get_templates(category="sales")
    # ... more rules
    
    # Default: Show all templates in relevant category
    return get_templates_by_category(infer_category(job_title))
```

---

#### 3. Template Granularity

**Decision**: Specific templates (Backend Engineer, Frontend Engineer) over broad (Engineer)

**Rationale**:
- More accurate evaluation - backend != frontend skill priorities
- Better candidate experience - evaluated on relevant criteria
- Easier to tune - adjust "Backend Engineer" without affecting "Frontend"
- Template library can grow based on customer requests

**V1 List**: 10-15 specific templates (see "System Default Templates" above)

---

#### 4. Skills Taxonomy Integration

**Decision**: No skills taxonomy in V1 - rely on LLM semantic matching

**Rationale**:
- Skills taxonomy maintenance is expensive (100,000+ skills across all domains)
- Modern LLMs (GPT-4, Claude) understand skill relationships natively
- Can iterate prompts faster than maintaining database
- V1 hypothesis: LLM matching is "good enough"

**Test in V1**: Measure false negative rate (candidate has skill but not matched)

**V2**: Add taxonomy if LLM matching has >10% error rate

**Example Skills Taxonomy** (for reference, not implementing in V1):
```json
{
  "Python": {
    "canonical_name": "Python",
    "aliases": ["python", "Python3", "Python 3", "python3", "py"],
    "category": "programming_language",
    "related_skills": {
      "frameworks": ["Django", "Flask", "FastAPI", "Pyramid"],
      "similar_languages": ["Ruby", "JavaScript", "Go"]
    },
    "proficiency_levels": ["beginner", "intermediate", "advanced", "expert"],
    "typical_years_to_proficiency": {
      "intermediate": 1,
      "advanced": 3,
      "expert": 5
    }
  }
}
```

---

### Implementation Checklist

#### Phase 1: ETS Foundation (Week 1)
- [ ] Create `evaluation_templates` table migration
- [ ] Add `evaluation_template_id` to `jobs` table
- [ ] Add `template_snapshot` to `evaluations` table
- [ ] Build CRUD API for templates (internal admin only)
- [ ] Create template seeding script

#### Phase 2: Default Templates (Week 2)
- [ ] Draft 10-15 template configurations (JSON)
- [ ] Review with domain experts (engineering, sales, etc.)
- [ ] Implement template validation schema
- [ ] Seed database with system defaults
- [ ] Create template preview API endpoint

#### Phase 3: Job Creation Integration (Week 3)
- [ ] Add template selection to job creation flow
- [ ] Implement auto-suggestion algorithm
- [ ] Update job creation API to accept `evaluation_template_id`
- [ ] Add template details to job response schema
- [ ] Frontend: Template selection UI component

#### Phase 4: Evaluation Integration (Week 4)
- [ ] Modify evaluation logic to use template configuration
- [ ] Implement dynamic score weighting
- [ ] Store template snapshot in evaluations
- [ ] Test with multiple templates
- [ ] Validate scoring consistency

#### Phase 5: Testing & Validation (Week 5)
- [ ] Test all 10-15 templates with real resumes
- [ ] Validate score distribution (should not all cluster at 50)
- [ ] A/B test weight variations
- [ ] Gather feedback from pilot users
- [ ] Iterate on template configurations

---

### Open Questions for V1.1 Implementation

1. **Template Selection UX**: Card-based gallery vs simple dropdown vs wizard?

2. **Template Preview**: How much detail to show before selection?
   - Full breakdown vs summary?
   - Sample evaluation output?

3. **Template Override**: Should recruiters be able to tweak weights per job? (Probably V2)

4. **Template Analytics**: Track which templates perform best (highest hire rate)?

5. **Template Migration**: If we update system template, offer jobs to migrate?

6. **Multi-template Jobs**: Can one job use multiple templates? (e.g., "Backend + ML Engineer")

7. **Template Marketplace**: Future: Community-contributed templates? (V3+)

---

## 1. Overview

**Purpose**: Automated candidate evaluation system that scores and ranks applicants against job requirements using LLM-powered analysis.

**Core Philosophy**:
- Data and accuracy over cost optimization
- Evaluation happens once per application (immutable after creation)
- Two-tier evaluation: (1) Candidate assessment, (2) Candidate-Job fit
- Modular architecture for easy iteration on models/prompts

---

## 2. Evaluation Trigger & Flow

### 2.1. When Evaluation Runs

**V1 Behavior** (MVP):
- Automatic async background task triggered immediately on application submission
- Single evaluation per application (no re-evaluation)
- Job description changes mark existing evaluations as "stale" (no auto re-trigger)

**Architecture Requirement**:
- Code must be modular to support future behaviors:
  - Manual on-demand evaluation
  - Re-evaluation when job description changes
  - Scheduled batch re-evaluation with improved models

### 2.2. Processing Flow

```
Application Submitted
    ↓
[Sync] Save application to DB (status: "applied")
    ↓
[Async] Trigger background task: evaluate_candidate()
    ↓
[Async] Step 1: Parse resume (extract text + metadata)
    ↓
[Async] Step 2: Run candidate evaluation (independent assessment)
    ↓
[Async] Step 3: Run candidate-job fit evaluation
    ↓
[Async] Save evaluation results to DB
    ↓
[Async] Update application.evaluation_status = "completed"
    ↓
[Frontend] Candidate appears in recruiter's pipeline with score/rank
```

**Error Handling**:
- Retry up to 2 times on failure (exponential backoff)
- After 2 failures: Set `evaluation_status = "failed"`
- Frontend shows "Evaluation Pending" badge with manual retry button
- Superadmin panel allows bulk retry for failed evaluations

---

## 3. Evaluation Framework

### 3.1. Chosen Approach

Based on research (see `temp-resources/ai-evaluation.md`), we adopt a **hybrid framework**:

- **Base**: A-FIT Framework (Alignment, Forte, Impact, Trajectory)
- **Enhanced**: Candidate Capability Profile dimensions
- **Output**: Structured scores + qualitative insights

### 3.2. Evaluation Types

#### Type 1: Independent Candidate Assessment
**Purpose**: Evaluate candidate quality independent of specific job  
**Use Case**: Training data, future job matching, analytics

**Evaluated Dimensions**:
1. **Technical Proficiency** (0-100)
   - Skill breadth and depth
   - Technology recency (recent vs outdated skills)
   - Evidence of hands-on application

2. **Experience Quality** (0-100)
   - Years of relevant experience
   - Career trajectory (progression, stability)
   - Company/industry context

3. **Impact & Achievements** (0-100)
   - Quantifiable results (e.g., "reduced costs by 40%")
   - Complexity of problems solved
   - Innovation indicators (patents, publications, awards)

4. **Professional Indicators** (0-100)
   - Inferred soft skills (leadership, collaboration, ownership)
   - Communication quality (resume clarity, structure)
   - Continuous learning (courses, certifications)

**Output**: Candidate profile stored for analytics, not shown to recruiters in V1.

---

#### Type 2: Candidate-Job Fit Evaluation
**Purpose**: Primary evaluation shown to recruiters - how well candidate matches THIS job

**Evaluated Dimensions** (A-FIT based):

1. **Alignment** (Weight: 40%)
   - **Skills Match** (70% of Alignment):
     - Must-have skills coverage
     - Nice-to-have skills coverage
     - Skill recency weighting
   - **Experience Level Match** (30% of Alignment):
     - Years of experience vs requirement
     - Seniority level match (entry/mid/senior/lead)

2. **Forte** (Weight: 30%)
   - **Role Relevance**: Semantic similarity of past titles to target role
   - **Responsibility Overlap**: LLM-scored similarity between past responsibilities and JD requirements
   - **Domain Experience**: Industry/company context match

3. **Impact** (Weight: 20%)
   - **Quantifiable Achievements**: Count and quality of measurable results
   - **Impact-Complexity Matrix**: Score achievements on both impact magnitude and technical complexity
   - **Highlights**: Top 3-5 standout accomplishments relevant to role

4. **Trajectory** (Weight: 10%)
   - **Career Growth**: Progression in responsibility/seniority
   - **Stability**: Job tenure patterns (red flags: <1 year stints)
   - **Relevance Trend**: Most recent experience alignment with target role

**Calculation**:
```
Overall Fit Score = (Alignment * 0.40) + (Forte * 0.30) + (Impact * 0.20) + (Trajectory * 0.10)
```

**Score Tiers**:
- 90-100: Top Tier / Priority Interview
- 75-89: Strong Fit / Interview
- 60-74: Potential Fit / Consider
- <60: Not a Fit

---

## 4. Storage Design

### 4.1. Storage Strategy: Hybrid Approach

**Decision**: Separate `evaluations` table + summary JSONB in `applications`

**Rationale**:
- Complex filtering/sorting by score, skills, dimensions (recruiter needs)
- Evaluation versioning for A/B testing and model improvements
- Support for dual evaluation types (candidate + job-fit)
- Performance: Indexed scores for fast queries

### 4.2. Database Schema

#### New Table: `evaluations`

```sql
CREATE TABLE evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES jobs(id),
    company_id UUID NOT NULL REFERENCES companies(id),
    
    -- Evaluation Type
    evaluation_type VARCHAR(50) NOT NULL,  -- 'candidate_assessment', 'job_fit'
    
    -- Overall Score
    overall_score NUMERIC(5,2),  -- 0-100, e.g., 87.50
    score_tier VARCHAR(50),  -- 'top_tier', 'strong_fit', 'potential_fit', 'not_fit'
    
    -- Dimension Scores (for job_fit type)
    alignment_score NUMERIC(5,2),
    forte_score NUMERIC(5,2),
    impact_score NUMERIC(5,2),
    trajectory_score NUMERIC(5,2),
    
    -- Detailed Breakdown (JSONB for flexibility)
    skills_breakdown JSONB,  -- Matched/missing skills, recency
    strengths JSONB,  -- Array of key strengths
    gaps JSONB,  -- Array of gaps/weaknesses
    highlights JSONB,  -- Top achievements relevant to role
    
    -- Qualitative Summary
    summary TEXT,  -- 2-3 paragraph LLM-generated summary
    recommended_questions JSONB,  -- Array of interview questions
    
    -- Model Metadata
    model_name VARCHAR(100),  -- e.g., "gpt-4-2024-01-25"
    model_version VARCHAR(50),  -- Internal prompt version, e.g., "v1.2"
    prompt_hash VARCHAR(64),  -- SHA256 of prompt used (for reproducibility)
    
    -- Cost Tracking
    tokens_used INTEGER,
    estimated_cost_usd NUMERIC(10,6),
    
    -- Performance Tracking
    latency_ms INTEGER,  -- Evaluation duration
    retry_count INTEGER DEFAULT 0,
    
    -- Status
    status VARCHAR(50) DEFAULT 'completed',  -- 'completed', 'failed', 'pending'
    error_message TEXT,
    
    -- Job Description Staleness
    job_description_hash VARCHAR(64),  -- Hash of JD at evaluation time
    is_stale BOOLEAN DEFAULT false,  -- True if JD changed after evaluation
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    evaluated_at TIMESTAMPTZ,
    
    CONSTRAINT valid_evaluation_type CHECK (
        evaluation_type IN ('candidate_assessment', 'job_fit')
    ),
    CONSTRAINT valid_evaluation_status CHECK (
        status IN ('pending', 'completed', 'failed')
    )
);

-- Indexes for common queries
CREATE INDEX idx_evaluations_application_id ON evaluations(application_id);
CREATE INDEX idx_evaluations_job_id ON evaluations(job_id);
CREATE INDEX idx_evaluations_company_id ON evaluations(company_id);
CREATE INDEX idx_evaluations_type ON evaluations(evaluation_type);
CREATE INDEX idx_evaluations_overall_score ON evaluations(overall_score DESC);
CREATE INDEX idx_evaluations_score_tier ON evaluations(score_tier);
CREATE INDEX idx_evaluations_status ON evaluations(status);
CREATE INDEX idx_evaluations_is_stale ON evaluations(is_stale);

-- Compound index for recruiter queries (filter by job + sort by score)
CREATE INDEX idx_evaluations_job_score ON evaluations(job_id, overall_score DESC);
```

#### Update: `applications` table

Add denormalized summary for fast access:

```sql
ALTER TABLE applications ADD COLUMN evaluation_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE applications ADD COLUMN evaluation_summary JSONB;

-- evaluation_status values: 'pending', 'processing', 'completed', 'failed'
```

**Example `evaluation_summary` JSONB**:
```json
{
  "overall_score": 87.5,
  "score_tier": "strong_fit",
  "top_strengths": ["Strong Python/FastAPI skills", "5+ years backend experience", "Led team of 4 engineers"],
  "top_gaps": ["No experience with Kubernetes", "Limited frontend exposure"],
  "evaluated_at": "2025-09-30T10:15:00Z"
}
```

---

### 4.3. Skills Breakdown JSONB Schema

```json
{
  "must_have_skills": {
    "required": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "matched": ["Python", "FastAPI", "PostgreSQL"],
    "missing": ["Docker"],
    "match_percentage": 75.0
  },
  "nice_to_have_skills": {
    "required": ["Kubernetes", "Redis", "AWS"],
    "matched": ["AWS"],
    "missing": ["Kubernetes", "Redis"],
    "match_percentage": 33.3
  },
  "skill_details": [
    {
      "skill": "Python",
      "match": true,
      "recency": "current",  // "current", "recent", "dated"
      "years_experience": 5,
      "proficiency_evidence": "Used in last 2 roles, led Python migration project"
    },
    {
      "skill": "Docker",
      "match": false,
      "mentioned_in_resume": false
    }
  ]
}
```

---

### 4.4. Highlights JSONB Schema

```json
{
  "top_highlights": [
    {
      "achievement": "Reduced API response time by 60% through optimization",
      "relevance_score": 95,
      "impact": "high",
      "complexity": "high"
    },
    {
      "achievement": "Led team of 4 engineers in microservices migration",
      "relevance_score": 88,
      "impact": "high",
      "complexity": "medium"
    }
  ]
}
```

---

## 5. Resume Parsing & Text Extraction

### 5.1. Strategy

**Current Approach**: Multimodal LLM (Gemini 2.5 Flash Lite)
- Cost-effective and accurate for text extraction
- Handles PDF/DOCX without external libraries
- Limitation: Cannot extract hyperlinks

**Hybrid Solution**:
1. Use library (e.g., `pypdf2`, `pdfplumber`) to extract raw text + links
2. Pass both raw text and display text to Gemini
3. LLM can reference links in context for better structured extraction

### 5.2. Parsed Resume Storage

**Decision**: Store permanently in `applications.resume_parsed_text` (TEXT column)

**Rationale**:
- Training data for future model improvements
- Re-evaluation without re-parsing (cost savings)
- Debugging and audit trail
- Future feature: Candidate profiles/accounts

**Additional Field** (already in schema):
```sql
ALTER TABLE applications ADD COLUMN resume_metadata JSONB;
```

**Example `resume_metadata` JSONB**:
```json
{
  "extraction_method": "gemini-2.5-flash-lite",
  "extracted_at": "2025-09-30T10:12:00Z",
  "file_size_bytes": 245800,
  "page_count": 2,
  "links_extracted": [
    {"text": "GitHub", "url": "https://github.com/username"},
    {"text": "Portfolio", "url": "https://portfolio.dev"}
  ],
  "extraction_confidence": 0.95
}
```

---

## 6. LLM Integration Architecture

### 6.1. BAML Integration

**Why BAML**:
- Type-safe structured outputs (Pydantic integration)
- Multi-provider support (OpenAI, Anthropic, Google)
- Hot-reloading for prompt iteration
- Built-in testing and versioning

**File Organization**:
```
llm/
  baml_src/
    resume_parser.baml         # Resume extraction prompt + types
    candidate_evaluator.baml   # Candidate assessment prompt
    job_fit_evaluator.baml     # Job-fit evaluation prompt
  baml_client/                 # Auto-generated client code
  prompts/
    resume_parsing_v1.txt      # Version-controlled prompts
    evaluation_v1.txt
  utils/
    baml_helpers.py            # Wrapper functions
  tests/
    test_evaluation.py         # LLM output validation tests
```

### 6.2. Model Selection Strategy

**Cost Tiers**:
1. **Parsing** (cheap): Gemini 2.5 Flash Lite (~$0.01/resume)
2. **Evaluation** (quality): GPT-4 Turbo or Claude 3.5 Sonnet (~$0.05-0.10/evaluation)

**Configurable via ENV**:
```python
RESUME_PARSER_MODEL = "gemini-2.5-flash-lite"
EVALUATOR_MODEL = "gpt-4-turbo-2024-04-09"
```

**Code Flexibility**:
- BAML client abstracts provider
- Easy A/B testing (e.g., 10% traffic to new model)
- Fallback chain: Primary model → Backup model → Fail

---

## 7. Versioning & Experiment Tracking

### 7.1. Evaluation Platform Integration

**Chosen Platform**: LangSmith (or similar)

**What We Track**:
- Token usage and cost per evaluation
- Latency (end-to-end evaluation time)
- Model/prompt version used
- Evaluation quality metrics (human feedback)

**Implementation**:
```python
from langsmith import traceable

@traceable(name="evaluate_candidate_job_fit")
async def evaluate_job_fit(resume_text, job_description, model_version):
    # LangSmith automatically logs inputs, outputs, latency, cost
    result = await baml_client.JobFitEvaluator(...)
    return result
```

### 7.2. Prompt Versioning

**Strategy**: Embed version in prompt metadata, store hash

```python
PROMPT_VERSION = "v1.2"
PROMPT_HASH = hashlib.sha256(prompt_text.encode()).hexdigest()
```

**Stored in `evaluations` table**:
- `model_version`: "v1.2"
- `prompt_hash`: "a3f5d8..."

**No "Outdated" Badge**: Customers see consistent experience, we track internally for improvement

### 7.3. A/B Testing Support

**Shadow Evaluations** (Internal):
- Run new model/prompt on subset of applications
- Store as separate evaluation record (`evaluation_type = 'shadow_test'`)
- Compare against production results
- No impact on recruiter-facing scores

---

## 8. Duplicate Application Prevention

### 8.1. Strategy

**Rule**: One application per email per job

**Implementation**:
```sql
-- Add unique constraint
CREATE UNIQUE INDEX idx_applications_job_email 
ON applications(job_id, LOWER(email));
```

**API Behavior**:
- Check constraint before accepting application
- Return friendly error: "You have already applied for this position"
- Frontend can also pre-check via API call

**Edge Cases**:
- Case-insensitive email matching (`LOWER(email)`)
- Allow same email to apply for different jobs
- Consider: What if candidate wants to update resume? (V2 feature)

---

## 9. Performance & Scalability

### 9.1. Expected Load

**V1 Targets**:
- 5-10 pilot clients
- ~5,000 applications/day max
- ~208 applications/hour avg
- ~3.5 applications/minute

**Bottleneck**: LLM API latency (~5-15 seconds per evaluation)

### 9.2. Async Task Queue

**Options**:
1. **Celery** (traditional, robust, needs Redis/RabbitMQ)
2. **Dramatiq** (lightweight, Redis-backed)
3. **Google Cloud Tasks** (serverless, no infra management)

**Recommendation**: Start with **Cloud Tasks** (fits Cloud Run serverless architecture)

**Queue Structure**:
```
Queue: "resume-parsing"    (high priority, fast)
Queue: "evaluation"        (normal priority, slower)
Queue: "retry-failed"      (low priority, manual trigger)
```

### 9.3. Caching Strategy

**What to Cache**:
- ❌ Don't cache evaluation results for reuse (candidate-job fit is unique)
- ✅ Cache job descriptions (avoid repeated DB queries)
- ✅ Cache parsed resume metadata (if re-parsing needed for debugging)

**Tool**: Redis for ephemeral caching

---

## 10. Error Handling & Observability

### 10.1. Failure Scenarios

| Scenario | Retry? | Fallback | User Impact |
|----------|--------|----------|-------------|
| LLM API timeout | Yes (2x) | Fail gracefully | "Evaluation Pending" badge |
| LLM rate limit | Yes (2x with backoff) | Fail gracefully | Same as above |
| Invalid LLM output | Yes (1x with schema repair) | Fail | Same |
| Resume parsing failure | Yes (1x) | Store raw text | Evaluation may be lower quality |
| Out of credits | No | Fail immediately | Alert superadmin |

### 10.2. Monitoring & Alerts

**Metrics to Track**:
- Evaluation success rate (target: >98%)
- Average latency (target: <10s)
- Cost per evaluation
- Failed evaluations queue depth

**Alerting**:
- Slack/email alert if failure rate >5%
- Daily cost report
- Weekly evaluation quality review

**Logging**:
- Structured JSON logs
- Include: `application_id`, `job_id`, `model_version`, `latency`, `cost`, `error`

---

## 11. Recruiter-Facing Features

### 11.1. Filtering & Sorting

**Supported Queries** (Frontend needs):
- Filter by score range: `score >= 75`
- Filter by score tier: `tier = 'strong_fit'`
- Filter by skill match: `skills_breakdown @> '{"must_have_skills": {"matched": ["Python"]}}'`
- Sort by score (default): `ORDER BY overall_score DESC`
- Sort by application date: `ORDER BY applied_at DESC`

**Implementation**: Indexed PostgreSQL queries, no full-text search needed in V1

### 11.2. Evaluation Detail View

**What Recruiter Sees** (candidate profile page):
- Overall score + tier badge
- Dimension breakdown (Alignment, Forte, Impact, Trajectory) with progress bars
- Skills match table (matched, missing, with recency indicators)
- Top 3-5 highlights (achievements relevant to job)
- Key strengths (bullet points)
- Gaps/areas to probe (bullet points)
- AI-generated summary (2-3 paragraphs)
- Suggested interview questions

**API Response**:
```json
{
  "evaluation": {
    "overall_score": 87.5,
    "score_tier": "strong_fit",
    "dimensions": {
      "alignment": 85.0,
      "forte": 92.0,
      "impact": 88.0,
      "trajectory": 80.0
    },
    "skills_breakdown": { ... },
    "strengths": ["Strong Python/FastAPI skills", "..."],
    "gaps": ["No K8s experience", "..."],
    "highlights": [ ... ],
    "summary": "This candidate demonstrates...",
    "interview_questions": ["Tell me about...", "..."]
  }
}
```

---

## 12. Staleness Detection

### 12.1. Strategy

When job description changes, mark existing evaluations as stale (don't auto re-evaluate).

**Implementation**:
```python
# On job update
old_jd_hash = hash_job_description(old_job.description)
new_jd_hash = hash_job_description(new_job.description)

if old_jd_hash != new_jd_hash:
    # Mark all job-fit evaluations for this job as stale
    await db.execute(
        "UPDATE evaluations SET is_stale = true WHERE job_id = $1 AND evaluation_type = 'job_fit'",
        job_id
    )
```

**Recruiter UI**:
- Show banner: "Job description updated. Evaluations may be outdated. [Re-evaluate All]"
- "Re-evaluate All" button triggers batch evaluation job (V2 feature, not implemented in V1)

**V1 Behavior**: Just mark as stale, inform recruiters manually

---

## 13. Open Questions & Deep Dive Topics

### 13.1. Needs Further Discussion

1. **Evaluation Schema Refinement**:
   - Is A-FIT weighting (40/30/20/10) optimal for our use case?
   - Should we customize weights per job role (e.g., senior roles weight Trajectory higher)?
   - Do we need a separate "Culture Fit" dimension?

2. **Resume Parsing Quality**:
   - What's our accuracy threshold for moving to production?
   - How do we handle non-standard resumes (creative layouts, portfolios)?
   - Should we support video resumes or GitHub profiles as alternatives?

3. **Skills Taxonomy**:
   - Do we need a canonical skills database (e.g., "React" = "ReactJS" = "React.js")?
   - How do we handle skill synonyms and related skills?
   - Should we use skill embeddings for semantic matching?

4. **Evaluation Explainability**:
   - How much detail is too much? (Risk: information overload for recruiters)
   - Should we include "confidence scores" for each dimension?
   - Do we need to cite specific resume sections in explanations?

5. **Bias & Fairness**:
   - How do we audit for demographic bias in evaluations?
   - Should we strip PII (name, gender indicators, age) before evaluation?
   - Compliance requirements (EEOC, GDPR)?

6. **Scalability**:
   - At what scale do we need to move from Cloud Tasks to dedicated queue?
   - Should we pre-warm LLM connections for lower latency?
   - Do we need evaluation result caching (e.g., same resume + same JD = cached score)?

---

## 14. Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Database schema (evaluations table, updated applications table)
- [ ] Resume parsing with Gemini (store parsed text)
- [ ] Basic BAML integration (single evaluation endpoint)
- [ ] Async task queue setup (Cloud Tasks)

### Phase 2: Core Evaluation (Week 3-4)
- [ ] Implement job-fit evaluation (A-FIT framework)
- [ ] Structured output schema (skills breakdown, highlights, etc.)
- [ ] Error handling and retry logic
- [ ] Basic observability (logging, cost tracking)

### Phase 3: Recruiter Features (Week 5)
- [ ] API endpoints for filtering/sorting candidates
- [ ] Evaluation detail view endpoint
- [ ] "Evaluation Pending" status handling
- [ ] Frontend integration

### Phase 4: Quality & Optimization (Week 6+)
- [ ] LangSmith integration for experiment tracking
- [ ] Prompt versioning system
- [ ] Duplicate application prevention
- [ ] Staleness detection
- [ ] Superadmin retry panel

---

## 15. Next Steps

1. **Review & Refine**: Go deeper on evaluation schema and weighting
2. **Prototype Prompt**: Draft initial BAML prompts for resume parsing and evaluation
3. **Test with Sample Data**: Run evaluation on 10-20 real resumes, validate output quality
4. **Finalize API Contracts**: Define exact request/response schemas for evaluation endpoints
5. **Set Up Dev Environment**: BAML, Cloud Tasks, LangSmith accounts

---

**Status**: Draft v1 - Ready for deep dive discussion  
**Last Updated**: 2025-09-30
