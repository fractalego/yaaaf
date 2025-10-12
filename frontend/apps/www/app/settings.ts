const port = process.env.YAAAF_API_PORT || 4000
console.log(`Using backend port as YAAAF_API_PORT=${port}`)

export const create_stream_url = `http://localhost:${port}/create_stream`
export const get_utterances_url = `http://localhost:${port}/get_utterances`
export const stream_utterances_url = `http://localhost:${port}/stream_utterances`
export const get_image_url = `http://localhost:${port}/get_image`
export const get_artefact_url = `http://localhost:${port}/get_artefact`
export const get_latest_todo_url = `http://localhost:${port}/get_latest_todo`
export const save_feedback_url = `http://localhost:${port}/save_feedback`

export const complete_tag = "<taskcompleted/>"
export const paused_tag = "<taskpaused/>"
export const query_suggestions: string =
  "who is the prime minister of Italy,what is the capital of France,how to cook pasta,what is the weather today,how to learn programming"

// Info button configuration
export const info_button_title = process.env.YAAAF_INFO_TITLE || "About YAAAF"
export const info_button_message =
  process.env.YAAAF_INFO_MESSAGE ||
  `YAAAF - Yet Another Autonomous Agents Framework

Contact: alberto@fractalego.io for any questions or issues.

🤖 Modular Agent System
Specialized agents for SQL, visualization, web search, ML, and more

⚡ Real-time Streaming
Live updates with structured responses and agent attribution

📊 Artifact Management
Centralized storage for generated content (tables, images, models)

🏷️ Tag-Based Routing
Use HTML-like tags for intuitive agent selection:
• <sqlagent> for database queries
• <visualizationagent> for charts and graphs
• <websearchagent> for web searches
• <bashagent> for filesystem operations

Start chatting to explore YAAAF's capabilities!`

console.log(
  `Using query suggestions as YAAAF_QUERY_SUGGESTIONS=${query_suggestions}`
)
console.log(`Using info button title as YAAAF_INFO_TITLE=${info_button_title}`)
