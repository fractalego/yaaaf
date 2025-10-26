import { PlanUpdate } from './plan-types';

export interface StreamingOptions {
  onMessage?: (content: string) => void;
  onPlanUpdate?: (update: PlanUpdate) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

export class StreamingChatClient {
  private baseUrl: string;

  constructor(baseUrl: string = '') {
    this.baseUrl = baseUrl;
  }

  async streamChat(message: string, options: StreamingOptions = {}) {
    try {
      const response = await fetch(`${this.baseUrl}/api/create_stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          stream: true
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No reader available');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
            options.onComplete?.();
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          
          // Process complete lines
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            if (line.trim() === '') continue;
            
            try {
              // Check if it's a server-sent event
              if (line.startsWith('data: ')) {
                const data = line.slice(6); // Remove 'data: ' prefix
                
                if (data === '[DONE]') {
                  options.onComplete?.();
                  return;
                }

                const parsed = JSON.parse(data);
                this.handleStreamedData(parsed, options);
              } else {
                // Regular message content
                options.onMessage?.(line);
              }
            } catch (parseError) {
              // If not JSON, treat as regular message content
              options.onMessage?.(line);
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch (error) {
      options.onError?.(error as Error);
    }
  }

  private handleStreamedData(data: any, options: StreamingOptions) {
    // Check if it's a plan update
    if (data.type && this.isPlanUpdateType(data.type)) {
      const planUpdate: PlanUpdate = {
        type: data.type,
        plan: data.plan,
        asset: data.asset,
        executionTime: data.executionTime,
        error: data.error,
        reason: data.reason,
        attempt: data.attempt,
        timestamp: data.timestamp || Date.now()
      };
      options.onPlanUpdate?.(planUpdate);
    } else if (data.content) {
      // Regular message content
      options.onMessage?.(data.content);
    } else if (typeof data === 'string') {
      // String content
      options.onMessage?.(data);
    }
  }

  private isPlanUpdateType(type: string): boolean {
    const planUpdateTypes = [
      'plan_created',
      'plan_updated', 
      'asset_started',
      'asset_completed',
      'asset_failed',
      'replanning',
      'plan_completed',
      'plan_failed'
    ];
    return planUpdateTypes.includes(type);
  }
}

// Default client instance
export const streamingClient = new StreamingChatClient();