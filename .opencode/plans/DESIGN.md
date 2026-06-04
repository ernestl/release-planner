# Release Planner UI/UX Design Specification

## Overview

This document describes the target UI/UX design for the snapd Release Planner web application. The design supports two viewing modes: a **Dashboard View** (normal mode) and a **Fullscreen Timeline View** (focused planning mode).

---

## Visual Style

- **Background**: White with soft shadows
- **Layout**: Clean, modern, rounded cards
- **Borders**: Light grey
- **Primary Accent Color**: Purple
- **Typography**: Modern sans-serif (Inter or similar)

---

## Color Palette

### **Semantic Colors**
- **Purple** (#6d28d9): Releases
- **Red** (#be123c): Deadlines
- **Orange** (#ea580c): Holidays
- **Blue** (#0369a1): Sprints
- **Green/Teal** (#14b8a6): Pulses

### **UI Colors**
- **Background**: #f8fafc
- **Surface**: #ffffff
- **Border**: #e2e8f0
- **Text**: #1e293b
- **Text Muted**: #64748b

---

## Layout Structure

### **1. Dashboard View (Normal Mode)**

#### **Top Navigation Bar**
- **Left Side**:
  - Product logo/icon: "snapd"
  - Navigation tabs: Roadmap, Releases, Sprints, Calendar, Reports
- **Right Side**:
  - Search box
  - Notification icon
  - User profile icon

#### **Left Sidebar (Overview)**
Fixed-width sidebar containing:

1. **Cycle Window Card**
   - Date range display
   - Duration information

2. **Next Major Release Card**
   - Version number (e.g., "2.76.0")
   - Date range (e.g., "Jun 30 - Jul 07")
   - Visual prominence (primary card style)

3. **Upcoming Deadline Card**
   - Deadline name (e.g., "Content Freeze")
   - Countdown display (e.g., "Jun 6 (28 days)")
   - Warning/attention styling

4. **Active Sprint Card**
   - Sprint name (e.g., "Virtual Sprint")
   - Date range (e.g., "Aug 12 - Jun 8")
   - Status indicator

5. **Legend**
   - Color-coded key:
     - 🟣 Releases
     - 🔴 Deadlines
     - 🟠 Holidays
     - 🔵 Sprints
     - 🟢 Pulse (P#)

#### **Main Content Area**
- **Page Header**:
  - Title: "snapd 26.10 Release Plan"
  - Green badge: "snapd"
  - Owner information
  - Generated timestamp

- **Summary Cards Section**:
  - Window (collapsible)
  - Included Sprints (collapsible)
  - Included Releases (collapsible)
  - Included Deadlines (collapsible)
  - Included Holidays (collapsible)

- **Release Timeline Section**:
  - Section title: "Release Timeline"
  - **Top-right controls**:
    - Zoom controls: Fit, 3M, 6M, 12M, All
    - Filter button
    - Export button
    - **Full screen button** (primary interaction)
  - Compact Gantt-style chart
  - Horizontal scrolling if needed

---

### **2. Fullscreen Timeline View (Expanded Mode)**

#### **Layout**
- Appears as a large floating panel/modal overlaying the dashboard
- White background with subtle shadow
- Takes up most of viewport (with margins)

#### **Header Bar**
- **Left Side**:
  - Product icon
  - Title: "snapd 26.10 Release Plan"
  - Hint text: "Esc to exit" (subtle, grey)

- **Right Side**:
  - **Exit full screen** button (outlined, prominent)

#### **Toolbar**
- **Zoom Controls** (button group):
  - Fit
  - 3M
  - 6M (selected/active by default)
  - 12M
  - All
- Buttons have clear active state (filled background)

#### **Timeline Visualization**

**Time Axis Rows**:
1. **MONTH Row**
   - Labels: "Jun 2026", "Jul 2026", "Aug 2026", etc.
   - Wide cells spanning multiple weeks
   - Subtle background color (#e8eff7)

2. **WEEK Row**
   - Labels: "W17", "W19", "W22", "W23", "W24", etc.
   - Circular or pill-shaped indicators
   - Date ranges below week numbers
   - Example: "W22" with "30-05 to 05-06"

3. **PULSE Row**
   - Green/teal cells spanning 2 weeks each
   - Labels: "P9", "P10", "P11", "P12", "P13", "P14", "P15"
   - Light green background (#d9efe9)
   - Teal text (#145a4d)

**Data Lanes**:

1. **RELEASES Lane**
   - Purple horizontal bars
   - **Three-line labels**:
     - Line 1: Version + purpose (e.g., "2.76 release: 26.04 carry-over")
     - Line 2: Date range (e.g., "May 19 - Jun 29")
   - Multiple rows for stacked releases (e.g., 2.76, 2.76.1, 2.76.2)
   - Gradient shading for sub-releases (lighter for .1, .2, etc.)
   - Dotted purple dependency arrows connecting to deadlines

2. **DEADLINES Lane**
   - **Red diamond markers** (◆)
   - Positioned on specific dates within week cells
   - **Three-line labels below diamonds**:
     - Line 1: Version number (bold red, e.g., "24.04.5")
     - Line 2: Milestone type (normal red, e.g., "Content Freeze")
     - Line 3: Date (small grey, e.g., "Aug 6")
   - Examples:
     - 24.04.5: Content Freeze, Final Release
     - 26.04.1: Content Freeze, Final Release
     - 26.10: Feature Freeze, Beta Freeze, Final Release
   - Vertically stacked when multiple deadlines for same release
   - Grouped by release version (same row)

3. **HOLIDAYS Lane**
   - Orange horizontal bars
   - **Two-line labels**:
     - Line 1: Holiday name (e.g., "Midyear Holiday")
     - Line 2: Date range (e.g., "Jul 27 - Aug 9")
   - Examples:
     - Midyear Holiday: Jul 27 - Aug 9
     - End-of-year Holiday: Dec 21 - Jan 3

4. **SPRINTS Lane**
   - Blue horizontal bars
   - **Two-line labels**:
     - Line 1: Sprint name (e.g., "May Sprint")
     - Line 2: Date range (e.g., "Apr 5 - May 17")
   - Examples:
     - May Sprint: Apr 5 - May 17
     - Virtual Sprint: May 17 - Jun 8
     - November Sprint: Oct 26 - Nov 8

**Visual Details**:
- All bars have rounded corners
- White text labels centered inside bars
- Subtle vertical grid lines separating weeks
- Lane backgrounds with light grey fills and borders
- Dependency arrows from releases to deadlines (dotted, purple, with arrowheads)

---

## User Interactions

### **1. Expand to Fullscreen**
**Trigger**: Click "Full screen" button in dashboard timeline section

**Action**:
1. Display overlay/modal with fullscreen timeline
2. Animate expansion (scale up, fade in)
3. Focus on timeline view
4. Hide surrounding dashboard elements
5. Show "Exit full screen" button and "Esc to exit" hint

**Result**: User sees large, focused timeline with zoom controls

---

### **2. Exit Fullscreen**
**Triggers**: 
- Click "Exit full screen" button (top-right)
- Press `Escape` key

**Action**:
1. Animate collapse (scale down, fade out)
2. Return to dashboard view
3. Restore sidebar and surrounding elements
4. Timeline returns to compact embedded view

**Result**: User returns to normal dashboard layout

---

### **3. Zoom Controls**
**Buttons**: Fit, 3M, 6M, 12M, All

**Behavior**:
- Click button to change zoom level
- Active button has filled background
- Timeline viewport adjusts to show:
  - **Fit**: Auto-fit to current window (6-month default)
  - **3M**: 3-month view
  - **6M**: 6-month view (default)
  - **12M**: 12-month view
  - **All**: Full project timeline
- Smooth transition animation
- Timeline scrolls horizontally if content exceeds viewport

---

### **4. Pan/Scroll Timeline**
**Behavior**:
- Horizontal scrolling (mouse wheel, trackpad, scrollbar)
- Drag to pan (click and drag on timeline)
- Timeline stays within bounds

---

### **5. Hover Tooltips**
**Behavior**:
- Hover over release bar → show full details
- Hover over deadline diamond → show full milestone info
- Hover over holiday/sprint → show date details
- Tooltip appears above/below element with arrow pointer

---

### **6. Filter (Future Enhancement)**
**Trigger**: Click "Filter" button

**Behavior**:
- Show dropdown with checkboxes:
  - ☑ Releases
  - ☑ Deadlines
  - ☑ Holidays
  - ☑ Sprints
- Toggle lane visibility
- Animate lane show/hide

---

### **7. Export (Future Enhancement)**
**Trigger**: Click "Export" button

**Behavior**:
- Show dropdown with options:
  - Export as PNG
  - Export as PDF
  - Export as SVG
  - Copy to clipboard
- Generate and download file

---

## Responsive Behavior

### **Desktop (1200px+)**
- Full sidebar visible
- Timeline scales to available width
- All features enabled

### **Tablet (768px - 1199px)**
- Sidebar collapsible (hamburger menu)
- Timeline shrinks proportionally
- Touch-friendly controls

### **Mobile (< 768px)**
- Sidebar hidden by default (drawer)
- Timeline scrolls horizontally
- Simplified controls
- Fullscreen mode becomes full viewport

---

## Accessibility

- **Keyboard Navigation**:
  - Tab through controls
  - Enter/Space to activate buttons
  - Escape to exit fullscreen
  - Arrow keys to pan timeline

- **Screen Reader Support**:
  - ARIA labels on all interactive elements
  - Semantic HTML structure
  - Alt text for icons
  - Descriptive tooltips

- **Color Contrast**:
  - WCAG AA compliant text contrast
  - Color + shape for differentiation (not color alone)

---

## Technical Implementation Notes

### **Timeline Rendering**
- Use SVG for timeline visualization
- Calculate positions in Python backend
- Pass coordinates to Jinja2 template
- Render as inline SVG in HTML

### **Fullscreen Mode**
- Use CSS to create modal overlay
- JavaScript to toggle fullscreen class
- CSS transitions for smooth animations
- Preserve timeline state (zoom, scroll position)

### **Zoom Levels**
- Pre-calculate zoom data in Python
- Pass multiple viewBox calculations to frontend
- JavaScript switches between viewBox values
- Animate viewBox transitions with CSS

### **Data Flow**
1. Python reads YAML
2. Python calculates timeline data, metrics, zoom levels
3. Python renders Jinja2 template with data
4. HTML includes embedded JSON data
5. JavaScript reads JSON and enables interactivity

### **GitHub Pages Deployment**
- Static HTML/CSS/JS output
- No server-side processing needed
- All assets in `output/` folder
- Relative paths for portability

---

## Key UX Principles

1. **Progressive Disclosure**: Start with dashboard overview, expand to detail
2. **Clear Hierarchy**: Visual weight guides attention (headers → cards → timeline)
3. **Obvious Actions**: Primary actions clearly labeled and positioned
4. **Reversible Actions**: Easy to exit fullscreen (button + keyboard)
5. **Consistent Language**: "Full screen" / "Exit full screen" pairing
6. **Visual Feedback**: Active states, hover effects, smooth transitions
7. **Information Density**: Dashboard is scannable; fullscreen is detailed
8. **Color Coding**: Consistent semantic colors with legend reference

---

## Future Enhancements

- **Drag-and-drop release scheduling**
- **Inline editing of dates/durations**
- **Real-time collaboration** (multi-user editing)
- **Saved views** (custom zoom/filter presets)
- **Timeline comparison** (compare multiple plans side-by-side)
- **Export to project management tools** (Jira, Asana, etc.)
- **Calendar integration** (sync deadlines to Google Calendar)
- **Notification system** (upcoming deadline alerts)

---

## Design Assets Needed

- **Icons**:
  - snapd logo
  - Navigation icons (roadmap, releases, sprints, calendar, reports)
  - Search icon
  - Notification bell icon
  - User profile icon
  - Fullscreen icon
  - Exit fullscreen icon
  - Filter icon
  - Export icon
  - Zoom icons

- **Fonts**:
  - Primary: Inter (Google Fonts)
  - Fallback: System sans-serif

- **Illustrations** (optional):
  - Empty state graphics
  - Error state graphics
  - Loading spinners

---

## Annotation Details from Mockup

### **Annotation 1: Expand Plan**
**Position**: Top center/right of mockup

**Text**:
> "1. Expand plan"
> "Click Full screen to expand"

**Visual**: Curved purple arrow pointing from text to fullscreen view

**Meaning**: This is the primary user flow - clicking the "Full screen" button in the dashboard timeline section expands the view into a focused fullscreen mode.

---

### **Annotation 2: Back to Dashboard**
**Position**: Lower-left of mockup

**Text**:
> "2. Back to dashboard"
> "Click Exit full screen or press Esc to return to the dashboard"

**Visual**: Curved purple arrow pointing from text back to dashboard view

**Meaning**: Users have two clear ways to exit fullscreen mode - clicking the "Exit full screen" button or pressing the Escape key. This returns them to the normal dashboard view with sidebar and surrounding context.

---

## Summary

The key UX concept is **dual-mode viewing**:

1. **Dashboard Mode**: Overview with sidebar metrics, summary cards, and compact timeline - optimized for quick scanning and context
2. **Fullscreen Mode**: Large focused timeline with zoom controls - optimized for detailed planning and analysis

The transition between modes is smooth, reversible, and clearly signposted. Users can quickly toggle between high-level overview and detailed timeline work without losing their place or context.
