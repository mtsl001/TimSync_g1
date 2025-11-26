
import { GoogleGenAI, Type, Schema } from "@google/genai";
import { Task, TaskPriority, SchedulePlan, UserPreferences } from "../types";

// Initialize Gemini Client
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

const MODEL_FAST = 'gemini-2.5-flash';

/**
 * Parses natural language input into a structured Task object.
 */
export const parseTaskFromInput = async (input: string): Promise<Partial<Task>> => {
  const responseSchema: Schema = {
    type: Type.OBJECT,
    properties: {
      title: { type: Type.STRING, description: "The concise title of the task" },
      description: { type: Type.STRING, description: "Additional details if provided" },
      durationMinutes: { type: Type.INTEGER, description: "Estimated duration in minutes. Default to 30 if unknown." },
      priority: { 
        type: Type.STRING, 
        enum: [TaskPriority.LOW, TaskPriority.MEDIUM, TaskPriority.HIGH],
        description: "Priority level based on urgency keywords (ASAP, urgent = HIGH)"
      },
    },
    required: ["title", "durationMinutes", "priority"]
  };

  try {
    const response = await ai.models.generateContent({
      model: MODEL_FAST,
      contents: `Extract task details from this user input: "${input}". infer priority and duration if not explicit.`,
      config: {
        responseMimeType: "application/json",
        responseSchema: responseSchema,
      },
    });

    if (response.text) {
      return JSON.parse(response.text);
    }
    return {};
  } catch (err) {
    console.error("Error parsing task:", err);
    throw err;
  }
};

/**
 * Generates an optimized schedule based on tasks and user preferences.
 */
export const generateOptimizedSchedule = async (tasks: Task[], prefs: UserPreferences): Promise<SchedulePlan> => {
  const responseSchema: Schema = {
    type: Type.OBJECT,
    properties: {
      scheduleName: { type: Type.STRING, description: "A creative name for the day's schedule" },
      items: {
        type: Type.ARRAY,
        items: {
            type: Type.OBJECT,
            properties: {
                taskId: { type: Type.STRING, description: "The ID of the task, or 'BREAK' for breaks" },
                startTime: { type: Type.STRING, description: "Start time in HH:MM format" },
                endTime: { type: Type.STRING, description: "End time in HH:MM format" },
                activityType: { type: Type.STRING, enum: ['Task', 'Break', 'Meeting'] },
                suggestion: { type: Type.STRING, description: "A short tip or motivation for this block" }
            },
            required: ["taskId", "startTime", "endTime", "activityType", "suggestion"]
        }
      },
      totalFocusTime: { type: Type.INTEGER, description: "Total minutes of work scheduled" }
    },
    required: ["scheduleName", "items", "totalFocusTime"]
  };

  const tasksJson = JSON.stringify(tasks.map(t => ({ id: t.id, title: t.title, duration: t.durationMinutes, priority: t.priority })));
  
  const prompt = `
    Create an optimized daily schedule.
    Start Time: ${prefs.startHour}:00
    End Time: ${prefs.endHour}:00
    Include Breaks: ${prefs.includeBreaks}
    
    Tasks to schedule:
    ${tasksJson}
    
    Rules:
    1. Prioritize HIGH priority tasks.
    2. Group similar tasks if possible.
    3. If includeBreaks is true, add short breaks (15m) every 90-120 mins.
    4. Ensure tasks fit within the start/end hours.
    5. Return valid JSON matching the schema.
  `;

  try {
    const response = await ai.models.generateContent({
        model: MODEL_FAST,
        contents: prompt,
        config: {
            responseMimeType: "application/json",
            responseSchema: responseSchema
        }
    });

    if (response.text) {
        return JSON.parse(response.text) as SchedulePlan;
    }
    throw new Error("Empty response from AI");
  } catch (error) {
      console.error("Error generating schedule:", error);
      throw error;
  }
};
