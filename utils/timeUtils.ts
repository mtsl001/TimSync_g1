
export const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Los_Angeles",
  "America/Chicago",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Dubai",
  "Asia/Singapore",
  "Australia/Sydney",
  "Pacific/Auckland"
];

export const getAvailableTimezones = () => {
  try {
    return (Intl as any).supportedValuesOf('timeZone');
  } catch (e) {
    return COMMON_TIMEZONES;
  }
};

export const formatTimeInZone = (date: Date, timeZone: string, format: 'digital' | 'analog' = 'digital') => {
  try {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      second: format === 'digital' ? '2-digit' : undefined,
      hour12: true,
      timeZone
    }).format(date);
  } catch (e) {
    return "Invalid Timezone";
  }
};

export const getAnalogHands = (date: Date, timeZone: string) => {
  try {
    const parts = new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric',
      hour12: false,
      timeZone
    }).formatToParts(date);
    
    const h = parseInt(parts.find(p => p.type === 'hour')?.value || '0');
    const m = parseInt(parts.find(p => p.type === 'minute')?.value || '0');
    const s = parseInt(parts.find(p => p.type === 'second')?.value || '0');

    const secondDeg = s * 6;
    const minuteDeg = m * 6 + s * 0.1;
    const hourDeg = (h % 12) * 30 + m * 0.5;

    return { hourDeg, minuteDeg, secondDeg };
  } catch (e) {
    return { hourDeg: 0, minuteDeg: 0, secondDeg: 0 };
  }
};

export const getDateInZone = (date: Date, timeZone: string) => {
  const options: Intl.DateTimeFormatOptions = { timeZone, weekday: 'short', month: 'short', day: 'numeric' };
  return new Intl.DateTimeFormat('en-US', options).format(date);
};

export const getHoursOffset = (timeZone: string) => {
  const date = new Date();
  const utcDate = new Date(date.toLocaleString('en-US', { timeZone: 'UTC' }));
  const tzDate = new Date(date.toLocaleString('en-US', { timeZone }));
  return (tzDate.getTime() - utcDate.getTime()) / 3600000;
};

export const isBusinessHour = (hour: number) => {
  return hour >= 9 && hour < 17;
};
