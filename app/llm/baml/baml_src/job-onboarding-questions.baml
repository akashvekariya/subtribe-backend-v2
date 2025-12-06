// Job Onboarding Questions Schema
// Generates onboarding calibration questions based on job details

enum SkillCategory {
  Technical @alias("technical")
  Soft @alias("soft")
  Domain @alias("domain")
}

enum SkillImportance {
  Critical @alias("critical")
  Important @alias("important")
  NiceToHave @alias("nice_to_have")
}

enum RoleComplexity {
  Junior @alias("junior")
  Mid @alias("mid")
  Senior @alias("senior")
  Lead @alias("lead")
  Executive @alias("executive")
}

// Extracted skill from job description
class ExtractedSkill {
  id string @description("Unique identifier for the skill, e.g., 'skill_python', 'skill_react'. Use lowercase with underscores.")
  name string @description("Display name of the skill, e.g., 'Python', 'React', 'Team Leadership'")
  category SkillCategory @description("Category: technical (programming, tools), soft (communication, leadership), or domain (industry-specific)")
  mentionCount int @description("How many times this skill is mentioned or implied in the JD. Minimum 1.")
  inferredImportance SkillImportance @description("Inferred importance based on placement, emphasis, and context in JD")
}

// Trade-off option for experience scenarios
class TradeoffOption {
  id string @description("Unique identifier, e.g., 'veteran', 'rising_star'")
  label string @description("Short display label, e.g., 'The Veteran'")
  description string @description("Brief description of this candidate profile")
  implication string @description("What choosing this option means for the hire")
}

// Trade-off scenario
class TradeoffScenario {
  id string @description("Unique identifier, e.g., 'experience_vs_potential'")
  title string @description("Scenario title, e.g., 'Experience vs Potential'")
  description string @description("Context for this trade-off based on the specific JD")
  options TradeoffOption[] @description("Exactly 2 options to choose from")
}

// Hidden requirement option
class HiddenRequirementOption {
  id string @description("Unique identifier for this option")
  label string @description("Display label")
  description string? @description("Optional description providing context")
}

// Hidden requirement question
class HiddenRequirementQuestion {
  id string @description("Question identifier: 'timezone', 'meeting_load', 'oncall'")
  label string @description("Question label shown to user")
  type string @description("Selection type: 'single_select' or 'multi_select'")
  options HiddenRequirementOption[] @description("Available options for this question")
}

// Skill reality check section
class SkillRealityCheck {
  mustHaveSkills ExtractedSkill[] @description("Skills that are absolutely required for this role - typically 5-8 skills marked as critical or explicitly required in the JD")
  goodToHaveSkills ExtractedSkill[] @description("Skills that would be beneficial but not strictly required - typically 5-10 skills that are nice-to-have or implied")
  instruction string @description("Instruction text for the user explaining the skill validation process")
}

// Experience trade-offs section
class ExperienceTradeoffs {
  scenarios TradeoffScenario[] @description("6-8 trade-off scenarios tailored to this specific role - covering experience, skills, culture, stability, and availability trade-offs")
}

// Hidden requirements section
class HiddenRequirements {
  questions HiddenRequirementQuestion[] @description("Questions about timezone, meeting load, on-call expectations")
}

// Honest assessment section
class HonestAssessment {
  challengeOptions string[] @description("5-7 potential challenges specific to this role, e.g., 'Legacy codebase', 'High pressure deadlines'")
  growthOpportunityQuestion string @description("A positive framing question about what would help someone thrive, e.g., 'What growth opportunities would help the right candidate succeed?'")
  growthOptions string[] @description("5-7 growth opportunities or support factors that would help someone thrive in this role")
  quitRiskOptions string[] @description("6-8 reasons someone might quit this role within 6 months - be honest about role/company challenges")
}

// Red flags and dealbreakers section
class RedFlagsSection {
  rejectionBehaviors string[] @description("7-8 candidate behaviors that would be automatic rejections for this role")
  trainableGaps string[] @description("5-6 skill gaps that the company would be willing to train for")
  nonTrainableGaps string[] @description("5-6 gaps that are NOT trainable and must be present on day 1")
}

// Role context section
class RoleContext {
  roleOpenReasons string[] @description("5 possible reasons why this role is open - team growth, backfill, new role, etc.")
  autonomyLevels string[] @description("4 levels of autonomy/guidance the new hire can expect")
  ambiguityLevels string[] @description("4 levels of role ambiguity/definition")
}

// Day 60 expectations section
class Day60Expectations {
  milestones string[] @description("5-7 realistic milestones for the first 60 days, derived from the JD responsibilities")
  instruction string @description("Instruction text, e.g., 'Select 2-3 key accomplishments you expect in the first 60 days'")
}

// Parsed job data
class ParsedJobData {
  extractedSkills ExtractedSkill[] @description("All skills found in the JD")
  suggestedResponsibilities string[] @description("Key responsibilities extracted/inferred from the JD")
  roleComplexity RoleComplexity @description("Assessed complexity level of this role")
  domainKeywords string[] @description("Industry/domain specific keywords found in the JD")
}

// Calibration questions payload
class CalibrationQuestionsPayload {
  skillRealityCheck SkillRealityCheck
  experienceTradeoffs ExperienceTradeoffs
  hiddenRequirements HiddenRequirements
  honestAssessment HonestAssessment
  redFlags RedFlagsSection
  roleContext RoleContext
  day60Expectations Day60Expectations
}

// Complete onboarding questions response
class JobOnboardingQuestionsResponse {
  parsedData ParsedJobData @description("Structured data extracted from the job description")
  calibrationQuestions CalibrationQuestionsPayload @description("Dynamic calibration questions generated based on the JD")
}

// Input job data
class JobInput {
  title string @description("Job title")
  description string @description("Full job description text")
  positionType string @description("Type: full_time, part_time, contract, internship")
  department string? @description("Department name if provided")
  locationType string @description("Location type: remote, onsite, hybrid")
  experienceMin int? @description("Minimum years of experience if specified")
  experienceMax int? @description("Maximum years of experience if specified")
}

function GenerateJobOnboardingQuestions(job: JobInput) -> JobOnboardingQuestionsResponse {
  client Gemini2_5FlashLite
  prompt #"
    {{ _.role("system") }}
    You are an expert recruiter and hiring manager assistant. Your task is to deeply analyze job descriptions
    and generate intelligent calibration questions that expose the REAL requirements behind the job posting.

    Most job descriptions are aspirational wish lists. Your job is to help hiring managers identify:
    1. What skills are ACTUALLY critical vs nice-to-have
    2. What trade-offs they're willing to make
    3. What hidden requirements exist that aren't in the JD
    4. What makes this role challenging
    5. What success looks like in the first 60 days

    IMPORTANT PRINCIPLES:
    - Be specific to THIS job, not generic
    - Generate options that force real choices (no "all of the above")
    - Use the actual terminology and context from the JD
    - Think like a seasoned recruiter who has seen hundreds of hires succeed and fail

    ---

    EXTRACTION RULES:

    1. SKILLS EXTRACTION (Split into two categories)
       MUST-HAVE SKILLS (5-8 skills):
       - Skills explicitly marked as "required", "must have", or in requirements section
       - Core technical skills that are fundamental to the role
       - Skills that appear multiple times or are heavily emphasized
       - Set inferredImportance to 'critical' for these
       - ALSO INFER 2-3 additional skills that are commonly needed for this type of role but not explicitly mentioned
         (e.g., if React is required, infer JavaScript; if AWS is required, infer cloud architecture basics)

       GOOD-TO-HAVE SKILLS (5-10 skills):
       - Skills in "nice to have", "preferred", or "bonus" sections
       - Skills implied but not explicitly required
       - Adjacent skills that would be helpful
       - Set inferredImportance to 'important' or 'nice_to_have' for these
       - ALSO INFER 2-3 additional complementary skills based on the tech stack and role
         (e.g., if backend role, infer API design; if senior role, infer mentoring)

       For BOTH categories:
       - Include: programming languages, frameworks, tools, methodologies, soft skills, domain expertise
       - Assign realistic mentionCount based on emphasis and repetition (use mentionCount=0 for inferred skills)
       - Generate unique IDs like: skill_python, skill_aws, skill_leadership

    2. TRADE-OFF SCENARIOS (Generate exactly 6-8)
       Each scenario forces a binary choice between two valid candidate profiles.
       Generate scenarios tailored to THIS specific role:

       Scenario 1: Experience vs Potential
       - "The Veteran" (10+ years, deep expertise, proven track record) vs
       - "The Rising Star" (3-5 years, high potential, current tech stack, eager to prove)

       Scenario 2: Specialist vs Generalist
       - "The Deep Specialist" (expert in core requirements) vs
       - "The Versatile Generalist" (broader skills, adapts quickly)

       Scenario 3: Culture vs Skill
       - "Culture Champion" (perfect culture fit, 70% skill match) vs
       - "Skill Master" (perfect skill match, unclear culture fit)

       Scenario 4: Stability vs Growth
       - "The Steady Hand" (stable 5yr tenure, consistent performer) vs
       - "The Fast Riser" (job hopper 18mo avg, rapid growth trajectory)

       Scenario 5: Pedigree vs Scrappiness
       - "The Pedigreed" (FAANG/top-tier background, structured approach) vs
       - "The Scrappy" (startup survivor, resourceful, self-taught)

       Scenario 6: Overqualified vs Stretch
       - "The Overqualified" (exceeds requirements, possible flight risk) vs
       - "The Stretch" (needs ramp-up time, high growth potential)

       Scenario 7: Known vs Unknown
       - "The Known Quantity" (referral, good-not-great reviews) vs
       - "The Wildcard" (unknown, stellar interview performance)

       Scenario 8: Availability vs Quality
       - "Available Now" (can start immediately, 80% fit) vs
       - "Worth the Wait" (perfect fit, 60-day notice period)

       IMPLICATION TEXT RULES (IMPORTANT):
       - Keep implications SHORT (max 15 words)
       - Focus on the TRADEOFF or RISK, not describing the candidate
       - Start with action words: "Expect...", "Risk:", "Tradeoff:", "Upside:", "Requires..."
       - NEVER start with "This candidate..." or similar phrases
       - Be direct and impactful

       Good examples:
       - "Risk: may leave for bigger challenges within 18 months"
       - "Expect slower ramp-up but long-term loyalty"
       - "Tradeoff: proven skills vs potential culture friction"
       - "Requires investment in mentorship and training"

       Bad examples (DO NOT USE):
       - "This candidate is likely to..." (too long, starts with "This candidate")
       - "They may be accustomed to..." (vague, passive)

    3. HIDDEN REQUIREMENTS
       Generate 3 questions:

       a) Timezone (id: 'timezone')
          Options based on role type:
          - For remote: offer major timezone ranges (Americas, Europe, Asia-Pacific, Flexible)
          - For onsite/hybrid: offer specific overlap requirements

       b) Meeting Load (id: 'meeting_load')
          Options: light (1-3 hrs/day), moderate (3-5 hrs/day), heavy (5+ hrs/day)
          Descriptions should reflect what that means for deep work time

       c) On-Call Expectations (id: 'oncall')
          Options: none, occasional (1-2x/month), regular (weekly rotation), primary (always available)
          Tailor to the role type (engineering vs non-engineering)

    4. HONEST ASSESSMENT (be brutally honest)
       Challenge Options (generate 5-7):
       - Infer from JD context what makes this role hard
       - Examples: "Legacy codebase", "Rapid growth chaos", "Cross-functional dependencies",
         "Ambiguous requirements", "High visibility/pressure", "Resource constraints"
       - Make them specific to what someone in THIS role would actually face

       Growth Opportunities (positive framing - generate 5-7):
       - Instead of asking why people leave, ask what would help someone thrive
       - Generate a positive question like: "What support would help the right candidate excel?"
       - Examples of growth options: "Mentorship from senior engineers", "Clear career progression path",
         "Opportunity to work on cutting-edge technology", "Cross-team collaboration",
         "Budget for learning and development", "Ownership of impactful projects"

       Quit Risk Options (generate 6-8):
       - What would make someone quit this role within 6 months?
       - Be honest about potential issues: "Lack of career growth", "Unrealistic expectations",
         "Poor work-life balance", "Toxic team dynamics", "Outdated tech stack",
         "Micromanagement", "Lack of impact/visibility", "Compensation below market"

    5. RED FLAGS & DEALBREAKERS
       Rejection Behaviors (generate 7-8):
       - Candidate behaviors that would be automatic rejections
       - Examples: "Badmouths previous employers", "Cannot explain job changes",
         "Unprepared for interview", "Arrogant/poor listener", "Salary expectations way off",
         "Ghosted previous rounds", "Lied on resume", "Negative attitude about challenges"

       Trainable Gaps (generate 5-6):
       - What skill gaps would the company train for?
       - Examples: "Specific programming language", "Domain knowledge", "Company-specific tools",
         "Leadership skills", "Presentation skills", "Industry certifications"

       Non-Trainable Gaps (generate 5-6):
       - What gaps are NOT trainable and must be present on day 1?
       - Examples: "Technical foundation", "Problem-solving ability", "Communication skills",
         "Cultural fit", "Work ethic", "Core domain expertise", "Years of relevant experience"

    6. ROLE CONTEXT
       Role Open Reasons (generate 5):
       - Why this role might be open
       - Options: "Team growth / new headcount", "Backfill - someone left",
         "Backfill - someone promoted", "New role - never existed", "Restructuring"

       Autonomy Levels (generate 4):
       - How much guidance/support the new hire will get
       - Options: "High guidance - lots of support and hand-holding",
         "Moderate - some guidance initially, then independence",
         "Self-directed - figure it out with minimal support",
         "Sink or swim - minimal support, high expectations"

       Ambiguity Levels (generate 4):
       - How well-defined is the role?
       - Options: "Clear roadmap - well-defined responsibilities",
         "Some ambiguity - direction set, details TBD",
         "High ambiguity - defining the role as you go",
         "Chaos - expect frequent pivots and changes"

    7. DAY 60 MILESTONES (generate 5-7)
       - Derive directly from the JD's responsibilities
       - Be specific and measurable where possible
       - Examples: "Ship first feature to production", "Complete team onboarding",
         "Own first project end-to-end", "Conduct first code review"
       - Think: What would a hiring manager realistically expect in 60 days?

    8. ROLE COMPLEXITY ASSESSMENT
       - junior: entry-level, learning focus, high supervision
       - mid: independent work, some ownership, 2-5 years typical
       - senior: significant ownership, mentoring others, 5+ years typical
       - lead: team leadership, architecture decisions, strategy
       - executive: department/org level impact, business strategy

    ---

    {{ _.role("user") }}
    Analyze this job posting and generate calibration questions:

    <job_input>
    Title: {{ job.title }}
    Position Type: {{ job.positionType }}
    Location Type: {{ job.locationType }}
    Department: {{ job.department }}
    Experience Required: {{ job.experienceMin }} - {{ job.experienceMax }} years

    Job Description:
    {{ job.description }}
    </job_input>

    Generate a complete JDParseResponse with:
    1. parsedData: Extract all skills, responsibilities, assess complexity, identify domain keywords
    2. calibrationQuestions: Generate all calibration sections with role-specific content

    {{ ctx.output_format }}
  "#
}
