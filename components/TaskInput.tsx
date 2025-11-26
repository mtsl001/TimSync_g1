import React, { useState } from 'react';
import { SparklesIcon, PlusIcon } from './Icons';
import { parseTaskFromInput } from '../services/geminiService';
import { Task } from '../types';
import { v4 as uuidv4 } from 'uuid'; // Fallback to simple random ID if uuid not available, but let's assume simple ID gen

interface TaskInputProps {
  onAddTask: (task: Task) => void;
}

const TaskInput: React.FC<TaskInputProps> = ({ onAddTask }) => {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSmartAdd = async () => {
    if (!input.trim()) return;
    setIsLoading(true);
    try {
      const partialTask = await parseTaskFromInput(input);
      const newTask: Task = {
        id: Math.random().toString(36).substr(2, 9),
        title: partialTask.title || input,
        description: partialTask.description || '',
        durationMinutes: partialTask.durationMinutes || 30,
        priority: partialTask.priority || 'Medium',
        isCompleted: false,
      } as Task;
      
      onAddTask(newTask);
      setInput('');
    } catch (err) {
      console.error(err);
      // Fallback
      onAddTask({
        id: Math.random().toString(36).substr(2, 9),
        title: input,
        durationMinutes: 30,
        priority: 'Medium',
        isCompleted: false
      } as Task);
      setInput('');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSmartAdd();
    }
  };

  return (
    <div className="relative mb-6">
      <div className="relative flex items-center">
        <div className="absolute left-3 text-slate-400">
          <SparklesIcon className="w-5 h-5" />
        </div>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask TimeSy: 'Draft report for 45 mins urgently'..."
          className="w-full pl-10 pr-12 py-4 bg-white border border-slate-200 rounded-xl shadow-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all text-slate-700 placeholder-slate-400"
          disabled={isLoading}
        />
        <button
          onClick={handleSmartAdd}
          disabled={isLoading || !input.trim()}
          className={`absolute right-2 p-2 rounded-lg transition-colors ${
            isLoading || !input.trim() 
              ? 'bg-slate-100 text-slate-400' 
              : 'bg-primary-600 text-white hover:bg-primary-700'
          }`}
        >
          {isLoading ? (
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <PlusIcon className="w-5 h-5" />
          )}
        </button>
      </div>
      <p className="mt-2 text-xs text-slate-500 ml-1">
        Try: <span className="italic">"Team meeting at 2pm for 1 hour"</span> or <span className="italic">"Code review ASAP"</span>
      </p>
    </div>
  );
};

export default TaskInput;