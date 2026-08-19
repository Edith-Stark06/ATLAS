---
name: Mission Control Adaptive System
colors:
  surface: '#11131b'
  surface-dim: '#11131b'
  surface-bright: '#373942'
  surface-container-lowest: '#0c0e15'
  surface-container-low: '#191b23'
  surface-container: '#1d1f27'
  surface-container-high: '#282a32'
  surface-container-highest: '#33343d'
  on-surface: '#e1e1ed'
  on-surface-variant: '#c2c6d6'
  inverse-surface: '#e1e1ed'
  inverse-on-surface: '#2e3039'
  outline: '#8c909f'
  outline-variant: '#424754'
  surface-tint: '#adc6ff'
  primary: '#adc6ff'
  on-primary: '#002e6a'
  primary-container: '#4d8eff'
  on-primary-container: '#00285d'
  inverse-primary: '#005ac2'
  secondary: '#4cd7f6'
  on-secondary: '#003640'
  secondary-container: '#03b5d3'
  on-secondary-container: '#00424e'
  tertiary: '#4edea3'
  on-tertiary: '#003824'
  tertiary-container: '#00a572'
  on-tertiary-container: '#00311f'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#acedff'
  secondary-fixed-dim: '#4cd7f6'
  on-secondary-fixed: '#001f26'
  on-secondary-fixed-variant: '#004e5c'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#11131b'
  on-background: '#e1e1ed'
  surface-variant: '#33343d'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.4'
  label-mono:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1'
    letterSpacing: 0.05em
  status-label:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: '1'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  container-padding: 24px
  gutter: 16px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style
The design system is engineered for high-stakes, mission-critical AI operations. The brand personality is authoritative, precise, and technologically advanced, evoking the feeling of a sophisticated command center. It targets enterprise operators and AI engineers who require immediate situational awareness and data-dense environments.

The visual style is a fusion of **Corporate Modern** and **Glassmorphism**, optimized for high performance. It utilizes deep layering, subtle luminescence, and a strict adherence to grid-based information density. The emotional response is one of absolute control, reliability, and "always-on" readiness.

## Colors
The palette is rooted in a "Deep Space" foundation to minimize eye strain during long-duration monitoring. 

- **Primary & Secondary:** Electric Blue and Cyan are used exclusively for interactive elements, primary actions, and active states.
- **Backgrounds:** Use `#0b0e15` for the base canvas and `#191b23` for persistent structural elements like sidebars and headers.
- **Semantic Colors:** Emerald (Success), Amber (Warning), and Red (Critical) are reserved for system status and data validation. These should often be paired with subtle glows to indicate urgency.
- **Accents:** Use low-opacity tints of the primary blue for hover states and selection rings.

## Typography
Typography prioritizes legibility in low-light environments. 

- **Headings:** Use Inter with tight letter-spacing and bold weights to establish a clear hierarchy.
- **Body:** Standardized on 14px for the majority of data views to maintain high information density without sacrificing readability.
- **Technical Data:** All IDs, hashes, coordinates, and system logs must use the monospaced **Geist** font to ensure character alignment and distinction between similar glyphs (e.g., 0 and O).
- **Labels:** Small, uppercase labels are used for metadata and status indicators to differentiate them from actionable text.

## Layout & Spacing
The layout follows a **Fluid Grid** model with a 4px base unit. This system is designed for high-density dashboards where horizontal real estate is at a premium.

- **Grid:** 12-column layout for desktop with 16px gutters.
- **Density:** Elements should be tightly packed but logically grouped using subtle background offsets rather than heavy margins. 
- **Adaptation:** On tablet, the grid shifts to 8 columns. On mobile, elements stack vertically, and secondary data visualizations are hidden or moved to drill-down views.
- **Modular Panels:** Content is organized into "Modules" or "Pods" that can be resized or rearranged, mimicking a terminal interface.

## Elevation & Depth
Depth is conveyed through **Tonal Layering** and **Glassmorphism** rather than traditional shadows.

- **Surfaces:** Use `#191b23` with 60-80% opacity and a `20px` backdrop blur for modals and floating panels.
- **Borders:** Every container should have a 1px solid border. Use `rgba(255, 255, 255, 0.08)` for standard containers and `rgba(59, 130, 246, 0.3)` for active/focused states.
- **Glows:** High-priority status indicators use a `0px 0px 8px` outer glow (drop-shadow with 0 spread) using the semantic color of the status.
- **Stacking:** Higher elevation is represented by lighter background tones and increased border opacity.

## Shapes
The shape language is "Soft-Industrial." 

- **Corners:** A base radius of `4px` (Soft) is applied to all buttons, inputs, and cards. This provides a professional, "machined" look that feels more precise than fully rounded corners.
- **Interactive Elements:** Buttons and form fields maintain consistent `4px` rounding.
- **Status Pips:** Small indicators (like online/offline dots) are the only fully circular elements in the system.

## Components
Consistent implementation of these components ensures the system feels like a unified toolset.

- **Buttons:** Primary buttons use a solid Electric Blue fill with white text. Secondary buttons use a ghost style with a thin border and no fill. All buttons feature a subtle 1px "inner highlight" on the top edge.
- **Data Inputs:** Fields use the Charcoal background with a 1px border. On focus, the border transitions to Cyan with a faint outer glow.
- **Status Indicators:** Use a "Glow-Pip" (a 6px circle with a matching color shadow) next to text labels.
- **Cards/Modules:** Use the glassmorphic style described in Elevation. Headers within cards should have a subtle bottom border.
- **Monitors/Chips:** For metadata tagging, use condensed chips with a dark fill and a border matching the category color. Use monospaced type for numerical chips.
- **Progress Bars:** Use slim (4px height) bars. Critical progress should use a pulsed animation effect.