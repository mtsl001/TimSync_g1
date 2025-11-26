
import React, { useState } from 'react';
import { TimezoneConfig } from '../types';
import { isBusinessHour, formatTimeInZone } from '../utils/timeUtils';

interface MeetingTimeFinderProps {
  timezones: TimezoneConfig[];
}

const MeetingTimeFinder: React.FC<MeetingTimeFinderProps> = ({ timezones }) => {
  const [selectedHour, setSelectedHour] = useState<number | null>(null);
  
  // Generate 24 hours
  const hours = Array.from({ length: 24 }, (_, i) => i);

  const getLocalHour = (baseHour: number, timezone: string) => {
    // This is a simplified calculation. For production precision, use complete Date objects.
    // Here we assume the baseHour is relative to UTC for visualization, 
    // or relative to the user's current time. Let's assume baseHour is UTC hour.
    const now = new Date();
    now.setUTCHours(baseHour, 0, 0, 0);
    const localStr = new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      hour12: false,
      timeZone: timezone
    }).format(now);
    return parseInt(localStr);
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="p-6 border-b border-slate-100">
        <h3 className="text-lg font-bold text-slate-900">Meeting Planner</h3>
        <p className="text-slate-500 text-sm">Find a time that works for everyone. Green blocks are business hours (9am - 5pm).</p>
      </div>

      <div className="overflow-x-auto pb-4">
        <div className="min-w-[800px] p-6">
          {/* Header Rows (Hours) */}
          <div className="flex mb-4 ml-32">
             {hours.map(h => (
               <div 
                 key={h} 
                 className={`flex-1 text-center text-xs text-slate-400 border-l border-slate-100 py-1 cursor-pointer transition-colors hover:bg-slate-50 ${selectedHour === h ? 'bg-primary-50 font-bold text-primary-600' : ''}`}
                 onClick={() => setSelectedHour(h)}
               >
                 {h}:00
               </div>
             ))}
          </div>

          {/* Timezone Rows */}
          <div className="space-y-3">
            {timezones.map(tz => (
              <div key={tz.id} className="flex items-center">
                <div className="w-32 flex-shrink-0 pr-4">
                  <div className="font-semibold text-sm text-slate-800 truncate">{tz.label}</div>
                  <div className="text-xs text-slate-500 truncate">{tz.timezone}</div>
                </div>
                <div className="flex-1 flex rounded-lg overflow-hidden border border-slate-100 h-10 bg-slate-50">
                   {hours.map(h => {
                     const localHour = getLocalHour(h, tz.timezone);
                     const isBiz = isBusinessHour(localHour);
                     const isSelected = selectedHour === h;
                     
                     return (
                       <div 
                         key={h}
                         className={`flex-1 flex items-center justify-center text-[10px] border-r border-white/50 cursor-pointer transition-all
                           ${isBiz ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-400'}
                           ${isSelected ? 'ring-2 ring-primary-500 z-10' : 'hover:opacity-80'}
                         `}
                         onClick={() => setSelectedHour(h)}
                         title={`${localHour}:00 in ${tz.label}`}
                       >
                         {localHour}
                       </div>
                     );
                   })}
                </div>
              </div>
            ))}
          </div>
          
          {/* Legend */}
          <div className="mt-6 flex items-center space-x-6 text-sm">
             <div className="flex items-center">
               <div className="w-4 h-4 bg-green-100 rounded mr-2 border border-green-200"></div>
               <span className="text-slate-600">Business Hours (9-17)</span>
             </div>
             <div className="flex items-center">
               <div className="w-4 h-4 bg-slate-100 rounded mr-2 border border-slate-200"></div>
               <span className="text-slate-600">Off Hours</span>
             </div>
          </div>
          
          {selectedHour !== null && (
             <div className="mt-6 p-4 bg-primary-50 rounded-xl border border-primary-100">
               <h4 className="font-semibold text-primary-900 mb-2">Selected Time: UTC {selectedHour}:00</h4>
               <ul className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                 {timezones.map(tz => {
                    const localHour = getLocalHour(selectedHour, tz.timezone);
                    return (
                      <li key={tz.id} className="text-slate-700">
                        <span className="font-medium text-slate-900">{tz.label}:</span> {localHour}:00 {localHour < 12 ? 'AM' : 'PM'}
                      </li>
                    )
                 })}
               </ul>
             </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default MeetingTimeFinder;
