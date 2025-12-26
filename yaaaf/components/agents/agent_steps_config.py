"""
Agent step limits configuration.

This module defines the maximum number of reflection steps each agent can take
before timing out. Lower values make agents faster but potentially less thorough.
"""

AGENT_MAX_STEPS = {
    # Single-step agents (no reflection needed)
    "answereragent": 1,
    "bravesearchagent": 1,
    "documentretrieveragent": 1,
    "planneragent": 1,  # Generates plan in one step
    "revieweragent": 1,
    "todoagent": 1,
    "urlagent": 1,
    "urlrevieweragent": 1,
    "userinputagent": 1,
    "websearchagent": 1,

    # Two-step agents (one reflection allowed)
    "bashagent": 2,
    "mleagent": 2,
    "numericalsequencesagent": 2,
    "sqlagent": 2,
    "toolagent": 2,
    "visualizationagent": 2,

    # Multi-step agents (can do multiple operations before completing)
    "codeeditagent": 5,  # May need to VIEW then STR_REPLACE
    "orchestratoragent": 15,  # Needs many steps to coordinate other agents
}

# Default for any agent not explicitly configured
DEFAULT_MAX_STEPS = 5