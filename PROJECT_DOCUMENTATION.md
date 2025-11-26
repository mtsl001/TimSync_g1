# TimeSync - Global Time Zone Converter

## 📋 Project Overview

TimeSync is a sophisticated web application for visualizing and managing multiple time zones simultaneously. It provides both digital and analog clock displays, real-time updates, meeting time finding capabilities, and sharing functionality.

### 🎯 Core Features
- **Multi-timezone Display**: View up to 6 different time zones simultaneously
- **Dual Clock Modes**: Switch between digital and analog clock displays
- **Real-time Updates**: Live time tracking with frozen time mode for specific moments
- **Meeting Time Finder**: Visual timeline to find optimal meeting times across time zones
- **Weather Integration**: Displays weather information and sunrise/sunset times
- **Sharing Functionality**: Export configurations and screenshots
- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile devices

---

## 🏗️ Architecture Overview

### Technology Stack
- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS 4 with shadcn/ui components
- **State Management**: React useState hooks
- **Real-time Communication**: Socket.IO
- **Icons**: Lucide React

### Project Structure
```
src/
├── app/                    # Next.js App Router
│   ├── page.tsx           # Main application page
│   ├── layout.tsx         # Root layout wrapper
│   └── globals.css        # Global styles and theme
├── components/            # React components
│   ├── WorldClock.tsx     # Main world clock component
│   ├── ClockDisplay.tsx   # Digital/analog clock rendering
│   ├── MeetingTimeFinder.tsx # Meeting timeline component
│   ├── TimezoneSelector.tsx # Timezone selection dialog
│   ├── Footer.tsx         # Application footer
│   └── ui/                # shadcn/ui component library
└── lib/                   # Utility libraries
    ├── timezone.ts        # Timezone data and utilities
    ├── weather.ts         # Weather simulation
    └── utils.ts           # General utilities
```

---

## 🧩 Component Breakdown

### 1. **Main Application** (`src/app/page.tsx`)
**Purpose**: Root application component managing global state and layout

**Key Responsibilities**:
- Header with branding and controls
- Time mode switching (Live vs Time Focused)
- Share functionality
- Main content orchestration

**State Management**:
```typescript
const [timezones, setTimezones] = useState<TimezoneCard[]>(DEFAULT_TIMEZONES);
const [selectedTime, setSelectedTime] = useState<Date | undefined>();
const [isLiveMode, setIsLiveMode] = useState(true);
const [showAnalog, setShowAnalog] = useState(false);
```

### 2. **WorldClock Component** (`src/components/WorldClock.tsx`)
**Purpose**: Renders timezone cards in a responsive grid layout

**Key Features**:
- Responsive grid system (configurable columns)
- Timezone card rendering with weather info
- Edit timezone functionality
- Day/night mode styling

**Customizable Grid Layout** (Line 189):
```typescript
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 justify-items-center">
```

### 3. **ClockDisplay Component** (`src/components/ClockDisplay.tsx`)
**Purpose**: Renders both digital and analog clock faces

**Digital Clock Features**:
- Monospace font display
- Real-time second updates
- Configurable sizes (sm, md, lg)

**Analog Clock Features**:
- SVG-based clock face
- Hour, minute, and second hands
- Timezone-specific time rendering

### 4. **MeetingTimeFinder Component** (`src/components/MeetingTimeFinder.tsx`)
**Purpose**: Visual timeline for finding optimal meeting times

**Key Features**:
- 24-hour timeline visualization
- Business hours highlighting
- Interactive time selection
- Meeting time recommendations

---

## 🎨 Styling and Theming

### Color System
The application uses a sophisticated color system defined in `src/app/globals.css`:

**Light Theme**:
- Background: `oklch(1 0 0)` (pure white)
- Primary: `oklch(0.205 0 0)` (dark slate)
- Cards: `oklch(1 0 0)` (white)
- Text: `oklch(0.145 0 0)` (dark gray)

**Dark Theme**:
- Background: `oklch(0.145 0 0)` (dark slate)
- Primary: `oklch(0.922 0 0)` (light gray)
- Cards: `oklch(0.205 0 0)` (medium slate)
- Text: `oklch(0.985 0 0)` (near white)

### Responsive Design
- **Mobile**: 1-2 columns, simplified controls
- **Tablet**: 2-3 columns, full functionality
- **Desktop**: 3-6 columns, optimal experience

### Component Styling
All components use Tailwind CSS classes with custom shadcn/ui components:
- Cards with hover effects and transitions
- Semantic color coding for business hours
- Day/night mode visual indicators

---

## ⚙️ Configuration Guide

### Modifying Grid Layout
**File**: `src/components/WorldClock.tsx`  
**Line**: 189

```typescript
// Current configuration
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 justify-items-center">

// For more columns
<div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3 justify-items-center">

// For larger cards
<div className="grid grid-cols-1 md:grid-cols-2 gap-8 justify-items-center">
```

### Customizing Colors
**File**: `src/app/globals.css`  
**Lines**: 46-113

Modify the CSS custom properties to change the theme:

```css
:root {
  --primary: oklch(0.205 0 0);        /* Change primary color */
  --background: oklch(1 0 0);         /* Change background */
  --card: oklch(1 0 0);              /* Change card background */
}
```

### Clock Display Customization
**File**: `src/components/ClockDisplay.tsx`

**Digital Clock Sizes** (Lines 29-33):
```typescript
const sizeClasses = {
  sm: 'text-xl',     // Small clocks
  md: 'text-3xl',    // Medium clocks  
  lg: 'text-5xl'     // Large clocks
};
```

**Analog Clock Sizes** (Lines 35-39):
```typescript
const analogSizeClasses = {
  sm: 'w-12 h-12',   // 48px × 48px
  md: 'w-20 h-20',   // 80px × 80px
  lg: 'w-28 h-28'    // 112px × 112px
};
```

---

## 🔧 Development Guide

### Running the Application
```bash
npm run dev          # Start development server
npm run build        # Build for production
npm run lint         # Run ESLint
```

### Key Development Files
- **`src/lib/timezone.ts`**: Timezone database and utilities
- **`src/lib/weather.ts`**: Weather simulation functions
- **`tailwind.config.ts`**: Tailwind CSS configuration
- **`components.json`**: shadcn/ui component configuration

### Adding New Features
1. Create new components in `src/components/`
2. Add utilities in `src/lib/`
3. Update types and interfaces
4. Test responsive design across breakpoints
5. Follow existing naming conventions

---

## 📱 Responsive Behavior

### Breakpoint System
- **Mobile** (< 640px): Single column, simplified UI
- **Small** (640px+): 2 columns, full features
- **Medium** (768px+): 2-3 columns
- **Large** (1024px+): 3 columns
- **XLarge** (1280px+): 3+ columns

### Component Adaptations
- Clock sizes adjust based on container
- Text scales appropriately
- Touch targets remain accessible
- Navigation adapts to screen size

---

## 🌍 Internationalization

### Timezone Support
- Comprehensive timezone database in `src/lib/timezone.ts`
- Automatic daylight saving time handling
- Proper timezone offset calculations
- Localized time formatting

### Date/Time Formatting
```typescript
// Example timezone formatting
formatTimeInTimezone(currentTime, timezone.timezone)
formatDateInTimezone(currentTime, timezone.timezone)
getTimezoneOffsetString(currentTime, timezone.timezone, baseTimezone.timezone)
```

---

## 🔒 Security Considerations

- No external API dependencies for core functionality
- Client-side timezone calculations
- Safe URL parameter handling for sharing
- Input sanitization in timezone selection

---

## 🚀 Performance Optimizations

- Efficient React state management
- Optimized re-rendering with proper dependencies
- SVG-based analog clocks for performance
- Lazy loading of heavy components
- Minimal external dependencies

---

## 📊 Browser Compatibility

### Supported Browsers
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### Required Features
- CSS Grid and Flexbox
- ES2020 JavaScript features
- SVG support
- CSS custom properties

---

## 🐛 Troubleshooting

### Common Issues
1. **Clock not updating**: Check `isLiveMode` state
2. **Layout breaking**: Verify responsive grid classes
3. **Timezone errors**: Ensure valid timezone identifiers
4. **Share functionality**: Check URL parameter handling

### Debug Tools
- React DevTools for component state
- Browser console for JavaScript errors
- Network tab for API requests
- Responsive design mode for layout testing

---

## 📚 API Reference

### Core Functions

#### Timezone Utilities (`src/lib/timezone.ts`)
```typescript
formatTimeInTimezone(date: Date, timezone: string): string
formatDateInTimezone(date: Date, timezone: string): string
getTimezoneOffsetString(date: Date, timezone: string, baseTimezone: string): string
isBusinessHours(date: Date, timezone: string): boolean
```

#### Weather Functions (`src/lib/weather.ts`)
```typescript
getWeatherData(city: string): WeatherData
getSunTimes(date: Date, timezone: string): SunTimes
```

### Component Props

#### WorldClock Props
```typescript
interface WorldClockProps {
  timezones: TimezoneCard[];
  selectedTime?: Date;
  isLiveMode: boolean;
  showAnalog: boolean;
  onToggleAnalog: () => void;
  onTimezoneChange: (id: string, updates: Partial<TimezoneCard>) => void;
  onReorder: (newOrder: TimezoneCard[]) => void;
  onTimeSelect: (time: Date) => void;
}
```

---

## 🔄 Future Enhancements

### Planned Features
- [ ] User timezone preferences persistence
- [ ] Additional clock themes and styles
- [ ] Calendar integration
- [ ] Advanced meeting scheduling
- [ ] Real weather API integration
- [ ] Mobile app version

### Technical Improvements
- [ ] Service worker for offline functionality
- [ ] Web Components for better encapsulation
- [ ] Advanced animation library
- [ ] Performance monitoring
- [ ] Automated testing suite

---

## 📞 Support and Contributing

### Getting Help
- Review this documentation
- Check component comments
- Examine existing code patterns
- Test with different browsers and devices

### Contributing Guidelines
1. Follow existing code style
2. Add appropriate TypeScript types
3. Test responsive behavior
4. Update documentation for new features
5. Ensure accessibility compliance

---

*This documentation is maintained alongside the application. Please update it when making significant changes to the codebase.*