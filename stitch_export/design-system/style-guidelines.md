## Brand & Style
The design system is engineered for high-stakes, mission-critical AI operations. The brand personality is authoritative, precise, and technologically advanced, evoking the feeling of a sophisticated command center. It targets enterprise operators and AI engineers who require immediate situational awareness and data-dense environments.

The visual style is a fusion of **Corporate Modern** and **Glassmorphism**, optimized for high performance. It utilizes deep layering, subtle luminescence, and a strict adherence to grid-based information density. The emotional response is one of absolute control, reliability, and "always-on" readiness.

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

## Components
Consistent implementation of these components ensures the system feels like a unified toolset.

- **Buttons:** Primary buttons use a solid Electric Blue fill with white text. Secondary buttons use a ghost style with a thin border and no fill. All buttons feature a subtle 1px "inner highlight" on the top edge.
- **Data Inputs:** Fields use the Charcoal background with a 1px border. On focus, the border transitions to Cyan with a faint outer glow.
- **Status Indicators:** Use a "Glow-Pip" (a 6px circle with a matching color shadow) next to text labels.
- **Cards/Modules:** Use the glassmorphic style described in Elevation. Headers within cards should have a subtle bottom border.
- **Monitors/Chips:** For metadata tagging, use condensed chips with a dark fill and a border matching the category color. Use monospaced type for numerical chips.
- **Progress Bars:** Use slim (4px height) bars. Critical progress should use a pulsed animation effect.