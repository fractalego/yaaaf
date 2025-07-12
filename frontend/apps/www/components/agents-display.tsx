"use client"

import { useEffect, useState } from "react"
import { Bot, ChevronDown, ChevronRight, Database, Wrench } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/registry/new-york/ui/collapsible"
import { Badge } from "@/registry/new-york/ui/badge"

interface AgentInfo {
  name: string
  description: string
  type: "agent" | "source" | "tool"
}

const TypeIcon = ({ type }: { type: string }) => {
  switch (type) {
    case "agent":
      return <Bot className="h-4 w-4" />
    case "source":
      return <Database className="h-4 w-4" />
    case "tool":
      return <Wrench className="h-4 w-4" />
    default:
      return <Bot className="h-4 w-4" />
  }
}

const TypeBadge = ({ type }: { type: string }) => {
  const colors = {
    agent: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    source: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
    tool: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  }

  return (
    <Badge
      variant="secondary"
      className={colors[type as keyof typeof colors] || colors.agent}
    >
      {type}
    </Badge>
  )
}

export function AgentsDisplay() {
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        // Use the backend port from environment or default to 4000
        const backendPort = "4000"
        const response = await fetch(
          `http://localhost:${backendPort}/get_agents_config`
        )
        if (!response.ok) {
          throw new Error(`Failed to fetch agents: ${response.statusText}`)
        }
        const data = await response.json()
        setAgents(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch agents")
      } finally {
        setLoading(false)
      }
    }

    fetchAgents()
  }, [])

  const groupedAgents = agents.reduce((acc, agent) => {
    if (!acc[agent.type]) {
      acc[agent.type] = []
    }
    acc[agent.type].push(agent)
    return acc
  }, {} as Record<string, AgentInfo[]>)


  if (loading) {
    return (
      <div className="border-b border-border/50 p-4">
        <div className="text-sm text-muted-foreground">Loading agents...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="border-b border-border/50 p-4">
        <div className="text-sm text-red-500">Error: {error}</div>
      </div>
    )
  }

  return (
    <div>
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-accent/50">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              {isOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              <span className="text-sm font-medium">Active Components</span>
            </div>
            <Badge variant="outline" className="text-xs">
              {agents.length}
            </Badge>
          </div>
        </CollapsibleTrigger>

        <CollapsibleContent className="pb-4">
          <div className="space-y-3 px-4">
            {Object.entries(groupedAgents).map(([type, typeAgents]) => (
              <div key={type} className="space-y-2">
                <div className="flex items-center gap-2">
                  <TypeIcon type={type} />
                  <span className="text-sm font-medium capitalize">
                    {type}s
                  </span>
                  <Badge variant="outline" className="text-xs">
                    {typeAgents.length}
                  </Badge>
                </div>
                <div className="ml-6 space-y-1">
                  {typeAgents.map((agent, index) => (
                    <div
                      key={index}
                      className="flex items-start gap-2 rounded-lg bg-accent/30 p-2"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-center gap-2">
                          <span className="truncate text-sm font-medium">
                            {agent.name}
                          </span>
                          <TypeBadge type={agent.type} />
                        </div>
                        <p className="text-xs leading-relaxed text-muted-foreground">
                          {agent.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
