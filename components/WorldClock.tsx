
import React, { useState, useEffect } from 'react';
import { TimezoneConfig } from '../types';
import ClockDisplay from './ClockDisplay';
import { PlusIcon, TrashIcon, SunIcon, MoonIcon } from './Icons';
import { getDateInZone, getHoursOffset, getAvailableTimezones } from '../utils/timeUtils';
import { v4 as uuidv4 } from 'uuid';

interface WorldClockProps {
  timezones: TimezoneConfig[];
  onUpdateTimezones: (newTimezones: TimezoneConfig[]) => void;
}

const WorldClock: React.FC<WorldClockProps> = ({ timezones, onUpdateTimezones }) => {
  const [isAdding, setIsAdding] = useState(false);
  const [newTz, setNewTz] = useState('UTC');
  const [newLabel, setNewLabel] = useState('');
  const [showAnalog, setShowAnalog] = useState(false);

  const availableTimezones = getAvailableTimezones();

  const handleAdd = () => {
    if (newLabel.trim()) {
      onUpdateTimezones([
        ...timezones, 
        { 
          id: uuidv4(), 
          timezone: newTz, 
          label: newLabel,
          isHome: false
        }
      ]);
      setIsAdding(false);
      setNewLabel('');
    }
  };

  const removeTimezone = (id: string) => {
    onUpdateTimezones(timezones.filter(tz => tz.id !== id));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h2 className="text-xl font-semibold text-slate-800">My Locations</h2>
        <div className="flex items-center space-x-3">
          <button
             onClick={() => setShowAnalog(!showAnalog)}
             className="text-sm text-slate-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Switch to {showAnalog ? 'Digital' : 'Analog'}
          </button>
          <button 
            onClick={() => setIsAdding(!isAdding)}
            className="flex items-center space-x-1 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors shadow-sm"
          >
            <PlusIcon className="w-4 h-4" />
            <span>Add Location</span>
          </button>
        </div>
      </div>

      {isAdding && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-lg animate-in fade-in slide-in-from-top-4">
          <h3 className="text-lg font-medium mb-4">Add New Timezone</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Label (City/Name)</label>
              <input 
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                placeholder="e.g. London Office"
                className="w-full p-2 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Timezone</label>
              <select 
                value={newTz}
                onChange={(e) => setNewTz(e.target.value)}
                className="w-full p-2 border border-slate-200 rounded-lg outline-none focus:ring-2 focus:ring-primary-500 bg-white"
              >
                {availableTimezones.map(tz => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex justify-end space-x-2">
            <button 
              onClick={() => setIsAdding(false)}
              className="px-4 py-2 text-slate-600 hover:bg-slate-50 rounded-lg"
            >
              Cancel
            </button>
            <button 
              onClick={handleAdd}
              className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              Add Clock
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {timezones.map((tz) => {
          const offset = getHoursOffset(tz.timezone);
          const isNight = new Date().toLocaleTimeString('en-US', { timeZone: tz.timezone, hour12: false }).split(':')[0] < '06' || 
                          new Date().toLocaleTimeString('en-US', { timeZone: tz.timezone, hour12: false }).split(':')[0] > '20';
          
          return (
            <div 
              key={tz.id}
              className={`relative p-6 rounded-2xl border transition-all hover:shadow-md ${
                isNight 
                  ? 'bg-slate-900 border-slate-800 text-white' 
                  : 'bg-white border-slate-200 text-slate-900'
              }`}
            >
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="font-bold text-lg">{tz.label}</h3>
                  <div className={`text-sm flex items-center gap-1 ${isNight ? 'text-slate-400' : 'text-slate-500'}`}>
                    <span>{getDateInZone(new Date(), tz.timezone)}</span>
                    <span>•</span>
                    <span>{offset >= 0 ? `+${offset.toFixed(1)}` : offset.toFixed(1)} hrs</span>
                  </div>
                </div>
                <div className={`p-2 rounded-full ${isNight ? 'bg-slate-800' : 'bg-orange-50'}`}>
                   {isNight ? <MoonIcon className="w-5 h-5 text-indigo-400" /> : <SunIcon className="w-5 h-5 text-orange-500" />}
                </div>
              </div>

              <div className="flex justify-center py-4">
                 <ClockDisplay 
                    timezone={tz.timezone} 
                    variant={showAnalog ? 'analog' : 'digital'} 
                    size={showAnalog ? 'md' : 'lg'}
                  />
              </div>

              <div className="mt-4 flex justify-between items-center">
                 <div className={`text-xs ${isNight ? 'text-slate-500' : 'text-slate-400'}`}>
                   {tz.timezone}
                 </div>
                 {!tz.isHome && (
                   <button 
                    onClick={() => removeTimezone(tz.id)}
                    className="p-1.5 text-red-400 hover:text-red-500 hover:bg-red-50/10 rounded"
                   >
                     <TrashIcon className="w-4 h-4" />
                   </button>
                 )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default WorldClock;
