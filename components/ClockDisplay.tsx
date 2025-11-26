
import React, { useEffect, useState } from 'react';
import { getAnalogHands, formatTimeInZone } from '../utils/timeUtils';

interface ClockDisplayProps {
  timezone: string;
  variant?: 'digital' | 'analog';
  size?: 'sm' | 'md' | 'lg';
  showSeconds?: boolean;
}

const ClockDisplay: React.FC<ClockDisplayProps> = ({ 
  timezone, 
  variant = 'digital', 
  size = 'md',
  showSeconds = true 
}) => {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  if (variant === 'analog') {
    const { hourDeg, minuteDeg, secondDeg } = getAnalogHands(time, timezone);
    const sizeClass = size === 'sm' ? 'w-16 h-16' : size === 'lg' ? 'w-48 h-48' : 'w-32 h-32';
    
    return (
      <div className={`relative ${sizeClass} bg-white rounded-full border-4 border-slate-100 shadow-inner flex items-center justify-center`}>
        {/* Clock Face Markers */}
        {[...Array(12)].map((_, i) => (
          <div 
            key={i} 
            className="absolute w-1 h-2 bg-slate-300 origin-bottom"
            style={{ 
              transform: `rotate(${i * 30}deg) translateY(-${size === 'sm' ? 24 : size === 'lg' ? 84 : 54}px)` 
            }}
          />
        ))}
        
        {/* Hands */}
        <div 
          className="absolute w-1.5 bg-slate-800 rounded-full origin-bottom"
          style={{ 
            height: '25%', 
            transform: `rotate(${hourDeg}deg)`, 
            bottom: '50%' 
          }} 
        />
        <div 
          className="absolute w-1 bg-slate-600 rounded-full origin-bottom"
          style={{ 
            height: '35%', 
            transform: `rotate(${minuteDeg}deg)`, 
            bottom: '50%' 
          }} 
        />
        {showSeconds && (
          <div 
            className="absolute w-0.5 bg-red-500 rounded-full origin-bottom"
            style={{ 
              height: '40%', 
              transform: `rotate(${secondDeg}deg)`, 
              bottom: '50%' 
            }} 
          />
        )}
        {/* Center Cap */}
        <div className="absolute w-3 h-3 bg-slate-800 rounded-full border-2 border-white z-10" />
      </div>
    );
  }

  // Digital
  const timeString = formatTimeInZone(time, timezone);
  const sizeClass = size === 'sm' ? 'text-xl' : size === 'lg' ? 'text-5xl font-light' : 'text-3xl';
  
  return (
    <div className={`font-mono text-slate-900 ${sizeClass}`}>
      {timeString}
    </div>
  );
};

export default ClockDisplay;
