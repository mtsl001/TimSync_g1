
import React, { useState, useEffect } from 'react';
import { Task, TaskPriority, SchedulePlan, ViewMode, UserPreferences, TimezoneConfig } from './types';
import TaskInput from './components/TaskInput';
import WorldClock from './components/WorldClock';
import MeetingTimeFinder from './components/MeetingTimeFinder';
import { 
  TrashIcon, 
  CalendarIcon, 
  ListIcon, 
  ClockIcon, 
  CheckCircleIcon, 
  SparklesIcon,
  MenuIcon,
  XIcon,
  SettingsIcon,
  EditIcon,
  GlobeIcon,
  UsersIcon
} from './components/Icons';
import { generateOptimizedSchedule } from './services/geminiService';
import { v4 as uuidv4 } from 'uuid';

const STORAGE_KEY_TASKS = 'timesy_tasks';
const STORAGE_KEY_PREFS = 'timesy_prefs';
const STORAGE_KEY_PLAN = 'timesy_plan';
const STORAGE_KEY_ZONES = 'timesy_zones';

const DEFAULT_PREFS: UserPreferences = {
  startHour: 9,
  endHour: 17,
  includeBreaks: true
};

const DEFAULT_ZONES: TimezoneConfig[] = [
  { id: '1', timezone: 'UTC', label: 'UTC', isHome: false },
  { id: '2', timezone: 'America/New_York', label: 'New York', isHome: true },
  { id: '3', timezone: 'Europe/London', label: 'London', isHome: false },
];

const App: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('tasks');
  const [schedulePlan, setSchedulePlan] = useState<SchedulePlan | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [userPrefs, setUserPrefs] = useState<UserPreferences>(DEFAULT_PREFS);
  const [timezones, setTimezones] = useState<TimezoneConfig[]>(DEFAULT_ZONES);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);

  // Load data on mount
  useEffect(() => {
    const savedTasks = localStorage.getItem(STORAGE_KEY_TASKS);
    const savedPrefs = localStorage.getItem(STORAGE_KEY_PREFS);
    const savedPlan = localStorage.getItem(STORAGE_KEY_PLAN);
    const savedZones = localStorage.getItem(STORAGE_KEY_ZONES);

    if (savedTasks) setTasks(JSON.parse(savedTasks));
    if (savedPrefs) setUserPrefs(JSON.parse(savedPrefs));
    if (savedPlan) setSchedulePlan(JSON.parse(savedPlan));
    if (savedZones) setTimezones(JSON.parse(savedZones));

    // Demo data for first time users
    if (!savedTasks && !localStorage.getItem('timeSy_visited')) {
      setTasks([
        { id: uuidv4(), title: 'Review Q3 Roadmap', durationMinutes: 60, priority: TaskPriority.HIGH, isCompleted: false },
        { id: uuidv4(), title: 'Email Marketing Sync', durationMinutes: 30, priority: TaskPriority.MEDIUM, isCompleted: false },
      ]);
      localStorage.setItem('timeSy_visited', 'true');
    }
  }, []);

  // Save data on change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_TASKS, JSON.stringify(tasks));
  }, [tasks]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_PREFS, JSON.stringify(userPrefs));
  }, [userPrefs]);

  useEffect(() => {
    if (schedulePlan) localStorage.setItem(STORAGE_KEY_PLAN, JSON.stringify(schedulePlan));
  }, [schedulePlan]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_ZONES, JSON.stringify(timezones));
  }, [timezones]);

  const addTask = (task: Task) => {
    setTasks(prev => [task, ...prev]);
  };

  const toggleTask = (id: string) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, isCompleted: !t.isCompleted } : t));
  };

  const deleteTask = (id: string) => {
    setTasks(prev => prev.filter(t => t.id !== id));
  };

  const clearCompleted = () => {
    if (window.confirm("Are you sure you want to remove all completed tasks?")) {
      setTasks(prev => prev.filter(t => !t.isCompleted));
    }
  };

  const updateTask = (id: string, updates: Partial<Task>) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, ...updates } : t));
    setEditingTaskId(null);
  };

  const handleGenerateSchedule = async () => {
    if (tasks.filter(t => !t.isCompleted).length === 0) {
      alert("No active tasks to schedule!");
      return;
    }
    
    setIsGenerating(true);
    try {
      const activeTasks = tasks.filter(t => !t.isCompleted);
      const plan = await generateOptimizedSchedule(activeTasks, { 
        startHour: userPrefs.startHour, 
        endHour: userPrefs.endHour 
      });
      setSchedulePlan(plan);
      setViewMode('schedule');
      setIsMobileMenuOpen(false);
    } catch (e) {
      alert("Could not generate schedule. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  };

  const NavItem = ({ mode, icon: Icon, label, badge, action }: any) => (
    <button
      onClick={() => {
        if (action) action();
        else setViewMode(mode);
        setIsMobileMenuOpen(false);
      }}
      className={`w-full flex items-center space-x-3 px-4 py-3 rounded-xl transition-all mb-1 ${
        viewMode === mode && !action
          ? 'bg-primary-50 text-primary-700 font-bold' 
          : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 font-medium'
      }`}
    >
      <Icon className={`w-5 h-5 ${viewMode === mode ? 'text-primary-600' : 'text-slate-400'}`} />
      <span>{label}</span>
      {badge && (
        <span className="ml-auto bg-white text-slate-500 text-xs py-0.5 px-2 rounded-full border border-slate-200 font-bold">
          {badge}
        </span>
      )}
    </button>
  );

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row font-sans text-slate-800">
      
      {/* Mobile Header */}
      <div className="md:hidden bg-white/80 backdrop-blur-md border-b border-slate-200 p-4 flex items-center justify-between sticky top-0 z-20">
        <div className="flex items-center space-x-2">
           <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-primary-500/30">
            TS
          </div>
          <span className="font-bold text-slate-900 text-lg">TimeSync</span>
        </div>
        <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="p-2 text-slate-600 rounded-lg hover:bg-slate-100">
          {isMobileMenuOpen ? <XIcon className="w-6 h-6" /> : <MenuIcon className="w-6 h-6" />}
        </button>
      </div>

      {/* Sidebar Overlay for Mobile */}
      {isMobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-20 md:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside className={`
        fixed md:sticky top-0 z-30 h-screen w-72 bg-white border-r border-slate-200 flex flex-col transition-transform duration-300 ease-in-out shadow-2xl md:shadow-none
        ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>
        <div className="hidden md:flex p-6 border-b border-slate-100 items-center space-x-3">
          <div className="w-9 h-9 bg-gradient-to-br from-primary-500 to-indigo-600 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg shadow-primary-500/30">
            TS
          </div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900">TimeSync</h1>
        </div>

        <nav className="p-4 flex-1 overflow-y-auto">
          <div className="mb-2 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Planning</div>
          <NavItem 
            mode="tasks" 
            icon={ListIcon} 
            label="Tasks" 
            badge={tasks.filter(t => !t.isCompleted).length} 
          />
          <NavItem 
            mode="schedule" 
            icon={CalendarIcon} 
            label="AI Schedule" 
            action={() => {
              if (schedulePlan) setViewMode('schedule');
              else handleGenerateSchedule();
            }}
          />

          <div className="mt-6 mb-2 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">Global Time</div>
          <NavItem 
            mode="world-clock" 
            icon={GlobeIcon} 
            label="World Clock" 
          />
          <NavItem 
            mode="meeting-finder" 
            icon={UsersIcon} 
            label="Meeting Planner" 
          />
          
          <div className="mt-6 mb-2 px-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">System</div>
          <NavItem 
            mode="settings" 
            icon={SettingsIcon} 
            label="Settings" 
          />
        </nav>

        <div className="p-4 border-t border-slate-100">
          <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-2xl p-4 text-white shadow-xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-3 opacity-10 group-hover:opacity-20 transition-opacity">
              <SparklesIcon className="w-12 h-12" />
            </div>
            <div className="flex items-center space-x-2 mb-2 relative z-10">
              <SparklesIcon className="w-4 h-4 text-yellow-400" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300">AI Assistant</span>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed mb-3 relative z-10">
              Optimize your workflow with Gemini AI.
            </p>
            <button 
              onClick={handleGenerateSchedule}
              disabled={isGenerating}
              className="w-full py-2.5 bg-white/10 hover:bg-white/20 border border-white/10 rounded-xl text-sm font-medium transition-all flex items-center justify-center space-x-2 relative z-10"
            >
              {isGenerating ? (
                 <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <span>Generate Plan</span>
              )}
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto h-[calc(100vh-65px)] md:h-screen p-4 md:p-8 lg:p-10 scroll-smooth">
        <div className="max-w-6xl mx-auto pb-20">
          
          {/* Header */}
          <header className="mb-10 flex flex-col md:flex-row md:items-center justify-between gap-4 animate-in fade-in slide-in-from-top-4 duration-500">
            <div>
              <h2 className="text-3xl font-bold text-slate-900 tracking-tight">
                {viewMode === 'tasks' && 'Task Board'}
                {viewMode === 'schedule' && (schedulePlan?.scheduleName || 'Daily Schedule')}
                {viewMode === 'world-clock' && 'Global Time'}
                {viewMode === 'meeting-finder' && 'Find Meeting Time'}
                {viewMode === 'settings' && 'Settings'}
              </h2>
              <p className="text-slate-500 mt-1 text-lg">
                {viewMode === 'tasks' && `Manage your priorities and deadlines.`}
                {viewMode === 'schedule' && `Estimated Focus Time: ${schedulePlan ? Math.floor(schedulePlan.totalFocusTime / 60) + 'h ' + (schedulePlan.totalFocusTime % 60) + 'm' : '0m'}`}
                {viewMode === 'world-clock' && 'Track time across your teams.'}
                {viewMode === 'meeting-finder' && 'Compare timezones to find the perfect slot.'}
                {viewMode === 'settings' && 'Customize your experience.'}
              </p>
            </div>
            <div className="text-sm font-medium bg-white px-5 py-2.5 rounded-full border border-slate-200 shadow-sm text-slate-600 flex items-center space-x-2">
              <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
              <span>{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</span>
            </div>
          </header>

          {/* TASKS VIEW */}
          {viewMode === 'tasks' && (
            <div className="space-y-8 animate-in fade-in zoom-in-95 duration-300">
              <TaskInput onAddTask={addTask} />
              
              <div className="flex justify-between items-end">
                 <h3 className="font-semibold text-slate-700">Active Tasks</h3>
                 {tasks.some(t => t.isCompleted) && (
                   <button 
                    onClick={clearCompleted}
                    className="text-sm text-red-500 hover:text-red-700 font-medium flex items-center px-3 py-1 rounded-lg hover:bg-red-50 transition-colors"
                   >
                     <TrashIcon className="w-4 h-4 mr-1" />
                     Clear Completed
                   </button>
                 )}
              </div>

              <div className="space-y-3">
                {tasks.length === 0 ? (
                  <div className="text-center py-24 bg-white rounded-3xl border-2 border-dashed border-slate-200">
                    <div className="mx-auto w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center text-slate-400 mb-4">
                      <ListIcon className="w-8 h-8" />
                    </div>
                    <h4 className="text-lg font-medium text-slate-900">All caught up!</h4>
                    <p className="text-slate-500 font-medium">Add a task above to get started.</p>
                  </div>
                ) : (
                  tasks.map(task => (
                    <div 
                      key={task.id} 
                      className={`group relative flex items-center p-5 bg-white border rounded-2xl shadow-sm hover:shadow-md transition-all duration-200 ${
                        task.isCompleted ? 'border-slate-100 bg-slate-50/80 opacity-75' : 'border-slate-200'
                      }`}
                    >
                      <button 
                        onClick={() => toggleTask(task.id)}
                        className={`flex-shrink-0 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all mr-5 ${
                          task.isCompleted 
                            ? 'bg-green-500 border-green-500 text-white scale-110' 
                            : 'border-slate-300 text-transparent hover:border-primary-500'
                        }`}
                      >
                        <CheckCircleIcon className="w-4 h-4" checked={task.isCompleted} />
                      </button>
                      
                      <div className="flex-1 min-w-0 pr-20">
                        {editingTaskId === task.id ? (
                           <input 
                              autoFocus
                              className="w-full font-medium text-lg text-slate-900 border-b-2 border-primary-500 outline-none bg-transparent"
                              defaultValue={task.title}
                              onBlur={(e) => updateTask(task.id, { title: e.target.value })}
                              onKeyDown={(e) => {
                                if(e.key === 'Enter') updateTask(task.id, { title: e.currentTarget.value });
                              }}
                           />
                        ) : (
                          <h3 className={`text-lg font-medium truncate cursor-pointer ${task.isCompleted ? 'text-slate-400 line-through' : 'text-slate-900'}`} onClick={() => setEditingTaskId(task.id)}>
                            {task.title}
                          </h3>
                        )}
                        
                        <div className="flex items-center space-x-3 mt-1.5 text-xs">
                          <span className={`px-2.5 py-1 rounded-md font-bold uppercase tracking-wide ${
                            task.priority === TaskPriority.HIGH ? 'bg-red-100 text-red-700' :
                            task.priority === TaskPriority.MEDIUM ? 'bg-orange-100 text-orange-700' :
                            'bg-blue-100 text-blue-700'
                          }`}>
                            {task.priority}
                          </span>
                          <span className="flex items-center text-slate-500 font-medium bg-slate-100 px-2 py-1 rounded-md">
                            <ClockIcon className="w-3 h-3 mr-1.5" />
                            {task.durationMinutes} min
                          </span>
                        </div>
                      </div>

                      <div className="absolute right-4 flex items-center space-x-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                        <button 
                          onClick={() => setEditingTaskId(task.id)}
                          className="p-2 text-slate-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                        >
                          <EditIcon className="w-5 h-5" />
                        </button>
                        <button 
                          onClick={() => deleteTask(task.id)}
                          className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        >
                          <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* SCHEDULE VIEW */}
          {viewMode === 'schedule' && schedulePlan && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
               <div className="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm mb-8">
                 <div className="flex items-center justify-between mb-6">
                    <h3 className="text-xl font-bold text-slate-900">Your Plan</h3>
                    <button onClick={handleGenerateSchedule} className="text-primary-600 text-sm font-medium hover:underline">Regenerate</button>
                 </div>
                 
                 <div className="relative border-l-2 border-slate-200 ml-3 space-y-8">
                    {schedulePlan.items.map((item, index) => {
                      const isBreak = item.activityType === 'Break';
                      const isMeeting = item.activityType === 'Meeting';
                      return (
                        <div key={index} className="relative pl-8 group">
                          {/* Time Marker */}
                          <div className={`absolute -left-[9px] top-0 w-4 h-4 rounded-full border-2 border-white shadow-sm z-10 transition-transform group-hover:scale-125 ${
                             isBreak ? 'bg-teal-400' : isMeeting ? 'bg-purple-400' : 'bg-primary-500'
                          }`}></div>
                          
                          <span className="absolute -left-20 top-[-4px] text-sm font-mono text-slate-400 w-12 text-right">
                            {item.startTime}
                          </span>
                          
                          <div className={`p-5 rounded-2xl border transition-all ${
                            isBreak ? 'bg-teal-50 border-teal-100' : 
                            isMeeting ? 'bg-purple-50 border-purple-100' :
                            'bg-white border-slate-200 hover:shadow-md'
                          }`}>
                            <div className="flex justify-between items-start mb-2">
                              <div>
                                <h4 className={`font-bold text-lg ${
                                  isBreak ? 'text-teal-900' : 
                                  isMeeting ? 'text-purple-900' : 
                                  'text-slate-900'
                                }`}>
                                  {item.taskId === 'BREAK' ? 'Refresh & Recharge' : tasks.find(t => t.id === item.taskId)?.title || 'Scheduled Activity'}
                                </h4>
                                <p className="text-sm opacity-80 mt-1 flex items-center">
                                  <ClockIcon className="w-3.5 h-3.5 mr-1.5" />
                                  {item.startTime} - {item.endTime}
                                </p>
                              </div>
                              {isBreak && (
                                <span className="bg-white/60 text-teal-700 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider shadow-sm">Break</span>
                              )}
                              {!isBreak && !isMeeting && (
                                <span className="bg-primary-50 text-primary-700 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider">Task</span>
                              )}
                            </div>
                            
                            {item.suggestion && (
                              <div className={`mt-3 p-3 rounded-xl text-sm flex items-start gap-2 ${
                                isBreak ? 'bg-white/60 text-teal-800' : 'bg-slate-50 text-slate-600'
                              }`}>
                                <SparklesIcon className="w-4 h-4 flex-shrink-0 mt-0.5 opacity-70" />
                                <span className="italic">"{item.suggestion}"</span>
                              </div>
                            )}
                          </div>
                        </div>
                      )
                    })}
                    
                    <div className="relative pl-8">
                      <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-slate-800 border-2 border-white shadow-sm z-10"></div>
                      <span className="absolute -left-20 top-[-4px] text-sm font-mono text-slate-900 font-bold w-12 text-right">
                          {userPrefs.endHour}:00
                        </span>
                      <div className="text-slate-400 text-sm italic pl-2">Great work today! 🎉</div>
                    </div>
                 </div>
               </div>
            </div>
          )}
          
          {viewMode === 'schedule' && !schedulePlan && !isGenerating && (
             <div className="text-center py-24 bg-white rounded-3xl border border-slate-200">
               <div className="w-20 h-20 bg-primary-50 rounded-full flex items-center justify-center mx-auto mb-6">
                 <CalendarIcon className="w-10 h-10 text-primary-400" />
               </div>
               <h3 className="text-xl font-bold text-slate-900">No schedule yet</h3>
               <p className="text-slate-500 mt-2 max-w-md mx-auto">
                 We need your tasks to build a schedule. Add some tasks and click "Generate Plan".
               </p>
               <button 
                onClick={handleGenerateSchedule}
                className="mt-8 px-8 py-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700 font-bold shadow-lg shadow-primary-500/30 transition-all hover:scale-105"
               >
                 Create Schedule
               </button>
             </div>
          )}

          {/* WORLD CLOCK VIEW */}
          {viewMode === 'world-clock' && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-300">
              <WorldClock 
                timezones={timezones} 
                onUpdateTimezones={setTimezones} 
              />
            </div>
          )}

          {/* MEETING FINDER VIEW */}
          {viewMode === 'meeting-finder' && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-300">
              <MeetingTimeFinder timezones={timezones} />
            </div>
          )}

          {/* SETTINGS VIEW */}
          {viewMode === 'settings' && (
             <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden animate-in fade-in zoom-in-95">
                <div className="p-8 border-b border-slate-100 bg-slate-50/50">
                  <h3 className="text-xl font-bold text-slate-900">Work Preferences</h3>
                  <p className="text-slate-500 text-sm mt-1">Customize your scheduling parameters.</p>
                </div>
                
                <div className="p-8 space-y-8">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">Start of Day</label>
                      <div className="relative">
                        <select 
                          value={userPrefs.startHour}
                          onChange={(e) => setUserPrefs(prev => ({ ...prev, startHour: parseInt(e.target.value) }))}
                          className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none appearance-none"
                        >
                           {Array.from({length: 24}, (_, i) => i).map(hour => (
                             <option key={hour} value={hour}>{hour}:00 {hour < 12 ? 'AM' : 'PM'}</option>
                           ))}
                        </select>
                        <ClockIcon className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5 pointer-events-none" />
                      </div>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">End of Day</label>
                      <div className="relative">
                        <select 
                           value={userPrefs.endHour}
                           onChange={(e) => setUserPrefs(prev => ({ ...prev, endHour: parseInt(e.target.value) }))}
                           className="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none appearance-none"
                        >
                           {Array.from({length: 24}, (_, i) => i).map(hour => (
                             <option key={hour} value={hour} disabled={hour <= userPrefs.startHour}>
                               {hour}:00 {hour < 12 ? 'AM' : 'PM'}
                             </option>
                           ))}
                        </select>
                        <ClockIcon className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 w-5 h-5 pointer-events-none" />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-4 p-5 bg-primary-50 rounded-xl border border-primary-100">
                    <input 
                      type="checkbox" 
                      id="breaks"
                      checked={userPrefs.includeBreaks}
                      onChange={(e) => setUserPrefs(prev => ({ ...prev, includeBreaks: e.target.checked }))}
                      className="w-6 h-6 text-primary-600 rounded focus:ring-primary-500 border-primary-200 cursor-pointer"
                    />
                    <label htmlFor="breaks" className="text-primary-900 font-bold cursor-pointer select-none">
                      AI Smart Breaks
                      <p className="text-primary-600 font-normal text-sm mt-0.5">Automatically insert 15-min refreshers between deep work blocks.</p>
                    </label>
                  </div>
                </div>
             </div>
          )}

        </div>
      </main>
    </div>
  );
};

export default App;
