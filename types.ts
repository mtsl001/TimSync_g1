
export enum TaskPriority {
  LOW = 'Low',
  MEDIUM = 'Medium',
  HIGH = 'High'
}

export interface Task {
  id: string;
  title: string;
  description?: string;
  durationMinutes: number; // Estimated duration
  priority: TaskPriority;
  isCompleted: boolean;
  scheduledTime?: string; // ISO String or HH:mm
}

export interface SchedulePlan {
  scheduleName: string;
  items: ScheduleItem[];
  totalFocusTime: number; // in minutes
}

export interface ScheduleItem {
  taskId: string;
  startTime: string; // HH:mm
  endTime: string; // HH:mm
  activityType: 'Task' | 'Break' | 'Meeting';
  suggestion: string; // AI suggestion on how to tackle it
}

export interface UserPreferences {
  startHour: number; // 9 for 9 AM
  endHour: number; // 17 for 5 PM
  includeBreaks: boolean;
}

export interface TimezoneConfig {
  id: string;
  timezone: string; // IANA timezone string (e.g. 'America/New_York')
  label: string;
  isHome?: boolean;
}

export type ViewMode = 'tasks' | 'schedule' | 'world-clock' | 'meeting-finder' | 'settings';
