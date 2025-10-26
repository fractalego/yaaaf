"use client";

import React, { useState } from 'react';
import { PlanExecutionView } from './plan-execution-view';
import { ExecutionPlan } from '@/lib/plan-types';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatMessageWithPlanProps {
  content: string;
  plan?: ExecutionPlan;
  isUser?: boolean;
  timestamp?: Date;
  className?: string;
}

export function ChatMessageWithPlan({
  content,
  plan,
  isUser = false,
  timestamp,
  className
}: ChatMessageWithPlanProps) {
  const [isPlanExpanded, setIsPlanExpanded] = useState(true);

  if (isUser) {
    return (
      <div className={cn("flex justify-end mb-4", className)}>
        <div className="max-w-[80%] bg-blue-500 text-white rounded-lg px-4 py-2">
          <p>{content}</p>
          {timestamp && (
            <div className="text-xs text-blue-100 mt-1">
              {timestamp.toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex justify-start mb-4", className)}>
      <div className="max-w-[90%] space-y-3">
        {/* Assistant Message */}
        <div className="bg-gray-100 rounded-lg px-4 py-3">
          <div className="prose prose-sm max-w-none">
            {content}
          </div>
          {timestamp && (
            <div className="text-xs text-gray-500 mt-2">
              {timestamp.toLocaleTimeString()}
            </div>
          )}
        </div>

        {/* Execution Plan */}
        {plan && (
          <div className="border rounded-lg bg-white shadow-sm">
            {/* Plan Header - Collapsible */}
            <button
              onClick={() => setIsPlanExpanded(!isPlanExpanded)}
              className="w-full flex items-center justify-between p-3 text-left hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-900">
                  Execution Plan
                </span>
                <span className="text-sm text-gray-500">
                  ({plan.assets.filter(a => a.status === 'completed').length}/{plan.assets.length} completed)
                </span>
              </div>
              {isPlanExpanded ? (
                <ChevronUp className="w-4 h-4 text-gray-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-gray-400" />
              )}
            </button>

            {/* Plan Content */}
            {isPlanExpanded && (
              <div className="border-t">
                <PlanExecutionView 
                  plan={plan} 
                  showDetails={true}
                  compact={false}
                />
              </div>
            )}

            {/* Compact View When Collapsed */}
            {!isPlanExpanded && (
              <div className="border-t p-3">
                <PlanExecutionView 
                  plan={plan} 
                  compact={true}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Example usage in chat component
export function ChatMessage({ 
  content, 
  plan, 
  isUser, 
  timestamp 
}: {
  content: string;
  plan?: ExecutionPlan;
  isUser?: boolean;
  timestamp?: Date;
}) {
  return (
    <ChatMessageWithPlan
      content={content}
      plan={plan}
      isUser={isUser}
      timestamp={timestamp}
    />
  );
}