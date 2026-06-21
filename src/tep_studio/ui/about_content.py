"""Verified content blocks for the About-the-TEP info page (rendered by layout._render_blocks).

Generated reference copy; edit prose here. Block types: para, subheading, bullets, reactions, note.
"""

ABOUT_SECTIONS = {
    "overview": {
        "title": "Overview",
        "blocks": [
            {
                "type": "para",
                "text": "The Tennessee Eastman Process (TEP) is a realistic, dynamic model of an industrial chemical plant. It is open-loop unstable: left to run on its own it does not settle into a steady state but drifts toward a shutdown. The underlying chemistry is based on a real Eastman Chemical process, but the actual reactants and products were disguised and relabeled as generic components so the model could be published without revealing proprietary details."
            },
            {
                "type": "para",
                "text": "The plant has five major units — a reactor, a condenser, a vapor/liquid separator, a recycle compressor, and a product stripper — fed by four input streams and producing two liquid products (G and H) alongside a byproduct (F) and an inert (B) that must be purged."
            },
            {
                "type": "subheading",
                "text": "Origin"
            },
            {
                "type": "para",
                "text": "The TEP was introduced by Downs and Vogel (1993) as an open challenge problem in plant-wide control. They published the model without a control scheme on purpose: the difficulty of stabilizing it, meeting product specifications, and rejecting disturbances simultaneously was left as the exercise. That framing made it equally useful as a benchmark for process monitoring and fault detection."
            },
            {
                "type": "subheading",
                "text": "Why it is the standard testbed"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Process control",
                        "text": "Plant-wide control, controller tuning, and constrained/economic optimization on a system that is unstable without active regulation."
                    },
                    {
                        "term": "Fault detection & diagnosis",
                        "text": "A fixed catalog of process disturbances provides labeled fault scenarios for monitoring, anomaly detection, and root-cause diagnosis."
                    },
                    {
                        "term": "Reinforcement learning",
                        "text": "A high-dimensional, partially observed, safety-constrained control environment with delayed consequences — a demanding RL benchmark."
                    }
                ]
            },
            {
                "type": "subheading",
                "text": "Chemistry"
            },
            {
                "type": "para",
                "text": "Eight components (A, B, C, D, E, F, G, H) participate in irreversible, exothermic gas-phase reactions. The gaseous reactants form two liquid products plus a byproduct:"
            },
            {
                "type": "reactions",
                "lines": [
                    "A + C + D  →  G        (product)",
                    "A + C + E  →  H        (product)",
                    "A + E      →  F        (byproduct)",
                    "3 D        →  2 F      (byproduct)"
                ]
            },
            {
                "type": "subheading",
                "text": "This simulator"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "8 components",
                        "text": "A, B, C, D, E, F, G, H."
                    },
                    {
                        "term": "50 internal states",
                        "text": "Holdups and energies across the reactor, separator, stripper, and feed header, plus the 12 valve positions."
                    },
                    {
                        "term": "41 measurements",
                        "text": "22 continuous process measurements and 19 sampled stream compositions."
                    },
                    {
                        "term": "12 manipulated variables",
                        "text": "The valve and agitator setpoints available to a controller."
                    },
                    {
                        "term": "28 disturbances",
                        "text": "Selectable fault modes, IDV(1) through IDV(28), spanning feed-composition shifts, temperature and pressure upsets, kinetics drift, and valve stiction."
                    }
                ]
            },
            {
                "type": "note",
                "text": "Run with no active control and the plant trips on a safety limit within roughly an hour — keeping it alive is the point of the exercise."
            }
        ]
    },
    "plant": {
        "title": "Plant & chemistry",
        "blocks": [
            {
                "type": "para",
                "text": "The plant is a five-unit gas-phase process knit together by a tight gas recycle loop. Fresh feeds and recycled gas enter an exothermic reactor; the product gas is cooled, separated, and the unreacted vapour is compressed back to the reactor, while liquid product is purified in a stripper."
            },
            {
                "type": "subheading",
                "text": "Unit operations"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Reactor",
                        "text": "Two-phase, exothermic. Feeds and recycle gas react over a catalyst; heat is removed by internal cooling. Reactor temperature is the key handle on product selectivity."
                    },
                    {
                        "term": "Partial condenser",
                        "text": "Cools the reactor effluent so the heavy products condense, leaving lighter unreacted species in the vapour."
                    },
                    {
                        "term": "Vapour–liquid separator",
                        "text": "Splits the condensed stream: liquid drops out to the stripper, vapour returns toward the reactor via the compressor."
                    },
                    {
                        "term": "Recycle compressor",
                        "text": "Raises the separator vapour back to reactor pressure, closing the tight gas recycle loop."
                    },
                    {
                        "term": "Product stripper",
                        "text": "Strips residual light components out of the liquid to deliver on-spec products G and H; stripped vapour rejoins the loop."
                    }
                ]
            },
            {
                "type": "note",
                "text": "Non-condensables and the inert B accumulate in the recycle loop and are bled off through a purge stream to hold pressure and inventory steady."
            },
            {
                "type": "subheading",
                "text": "Reactions"
            },
            {
                "type": "para",
                "text": "Four irreversible, exothermic, gas-phase reactions occur in the reactor — two forming liquid products, two forming byproduct:"
            },
            {
                "type": "reactions",
                "lines": [
                    "A + C + D  →  G        (liquid product)",
                    "A + C + E  →  H        (liquid product)",
                    "A + E      →  F        (byproduct)",
                    "3 D        →  2 F      (byproduct)"
                ]
            },
            {
                "type": "subheading",
                "text": "Components"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Reactants — A, C, D, E",
                        "text": "Gas-phase feeds consumed by the reactions."
                    },
                    {
                        "term": "Inert — B",
                        "text": "Non-reacting; accumulates in the loop and is removed by the purge."
                    },
                    {
                        "term": "Byproduct — F",
                        "text": "Undesired species from the A + E and 3 D reactions."
                    },
                    {
                        "term": "Products — G, H",
                        "text": "Liquid products recovered through the separator and stripper."
                    }
                ]
            },
            {
                "type": "note",
                "text": "Reactor temperature shifts selectivity between the two products: lower temperature favours G, higher temperature favours H."
            }
        ]
    },
    "control": {
        "title": "Control strategy",
        "blocks": [
            {
                "type": "para",
                "text": "The plant is open-loop unstable — left alone it trips on reactor pressure within about an hour. TEP Studio holds it with a built-in decentralized multiloop PI strategy: a set of simple, single-input single-output PI loops, each governing one part of the plant, that together keep inventories, temperature, and pressure inside their trip limits while delivering the requested product. There is no central optimizer; the loops are tuned to cooperate."
            },
            {
                "type": "subheading",
                "text": "How the loops fit together"
            },
            {
                "type": "para",
                "text": "Everything is anchored to a single throughput knob and a set of ratios, so the whole plant scales up or down coherently."
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Production-rate loop",
                        "text": "A slow outer loop watches the stripper product flow and trims an overall production index (Fp). Fp starts at a nominal 100 and the loop adds a bounded adjustment (limited to +/-30). This single index sets the scale for the entire plant."
                    },
                    {
                        "term": "Seven feed/flow ratio loops",
                        "text": "Each of the four feeds (A, C, D, E), the purge, the separator underflow, and the stripper underflow runs a fast valve loop whose flow target is a fixed ratio (r1..r7) times the production index. When Fp moves, all seven targets move with it, so feeds and draws stay in proportion and the plant throughput changes as a unit."
                    },
                    {
                        "term": "Inventory cascades",
                        "text": "Liquid levels are held without letting any vessel run dry or flood. The reactor-level loop does not move a valve directly — it sets the separator-temperature target (a cascade), and a faster separator-temperature loop then drives the condenser cooling-water valve. The separator-level and stripper-level loops adjust their own underflow ratios (r6 and r7), tightening the link between level and draw-off."
                    },
                    {
                        "term": "Reactor temperature → reactor cooling",
                        "text": "A dedicated loop holds reactor temperature by modulating the reactor cooling-water valve."
                    },
                    {
                        "term": "Reactor pressure → purge",
                        "text": "Reactor pressure is regulated by the purge: the pressure loop sets the purge ratio (r5), venting more or less of the gas loop to keep pressure off the trip limit. (Pressure is held by purging, not by the compressor recycle valve.)"
                    },
                    {
                        "term": "Composition control",
                        "text": "Product G/H is set mostly by feedforward: the D-feed and E-feed ratios (r2, r3) are computed from the target %G via fixed calibration curves. An optional %G feedback trim is available but is off by default (it needs retuning for this plant variant). Two reactant-composition trims — yA and yAC — make slow velocity-form corrections to the A-feed and C-feed ratios to keep the reactor feed mix on target."
                    }
                ]
            },
            {
                "type": "subheading",
                "text": "Smooth transitions and safety overrides"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Rate-limited setpoints",
                        "text": "The production-rate and %G targets are ramped, not stepped. When you change modes, the controller walks these slow, feed-driven setpoints toward their new values gradually, which avoids the large transient that would otherwise trip the plant on an operating-point change."
                    },
                    {
                        "term": "High-pressure override",
                        "text": "If reactor pressure climbs past a guard threshold (below the trip limit), an override cuts the production index in proportion to the excess, throttling throughput to stay inside the limit. On by default as a safety function; it can be toggled via the Controller flags."
                    },
                    {
                        "term": "High-level override",
                        "text": "If reactor level rises too high, an override closes down the compressor recycle valve to relieve the vessel. On by default as a safety function; it can be toggled via the Controller flags."
                    }
                ]
            },
            {
                "type": "subheading",
                "text": "Parked manipulated variables"
            },
            {
                "type": "para",
                "text": "Three of the twelve manipulated variables are not on feedback loops in this strategy — they are held fixed at their nominal positions:"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Compressor recycle valve",
                        "text": "Fixed, unless the high-level override acts on it."
                    },
                    {
                        "term": "Stripper steam valve",
                        "text": "Fixed."
                    },
                    {
                        "term": "Reactor agitator speed",
                        "text": "Fixed."
                    }
                ]
            },
            {
                "type": "subheading",
                "text": "Operating modes"
            },
            {
                "type": "para",
                "text": "An operating mode is simply a set of controller setpoints — chiefly the G:H product ratio (via the %G target) and the production rate. Selecting a mode changes the targets the loops chase; it does not swap in a different controller."
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Mode 1",
                        "text": "The base case (50/50 G:H, base rate)."
                    },
                    {
                        "term": "Modes 2, 4, 5",
                        "text": "Reached by steering from the base state: the run starts at the base steady state and the closed loop drives the plant to the new setpoints (different G:H and/or a modest production increase)."
                    },
                    {
                        "term": "Modes 3 and 6 (90/10)",
                        "text": "The extreme 90/10 composition cannot be reached from the base case without a high-pressure trip, so these modes start from a bundled 90/10 operating-point state and the controller simply holds it. Mode 6 attempts a modest production increase above mode 3."
                    }
                ]
            },
            {
                "type": "note",
                "text": "\"Max\"-production modes (4, 5, 6) request a small increase over the base rate; a feed eventually saturates, capping throughput at that constraint."
            },
            {
                "type": "subheading",
                "text": "Everything here is editable"
            },
            {
                "type": "para",
                "text": "This strategy is the default, not a fixed wiring. In the studio you can edit the controller tuning table (gains, reset times, ratios, and limits for every loop), set a custom initial state, and toggle the controller on/off flags — including the composition feedforward, the optional %G feedback, and the two safety overrides — to run your own control configuration."
            },
            {
                "type": "note",
                "text": "This decentralized multiloop strategy follows N. L. Ricker, “Decentralized control of the Tennessee Eastman challenge process,” Journal of Process Control 6(4), 205–221, 1996."
            }
        ]
    },
    "usage": {
        "title": "Using the studio",
        "blocks": [
            {
                "type": "para",
                "text": "The studio is organized into four tabs. Configure and run a simulation in Simulate, turn runs into datasets in Dataset, overlay runs in Compare, and inspect KPIs plus pull a reproducible record in Metrics / Record."
            },
            {
                "type": "subheading",
                "text": "Simulate"
            },
            {
                "type": "para",
                "text": "The left card configures a run; the right card plots it. Set it up top to bottom, then press Run simulation."
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Operating mode",
                        "text": "Pick one of the six standard modes (G:H ratio × production rate). The mode sets the controller setpoints and the default initial state."
                    },
                    {
                        "term": "Loop",
                        "text": "Closed loop reveals the setpoint editor; open loop swaps it for direct manipulated-variable (MV) sliders, holding the valves where you place them."
                    },
                    {
                        "term": "Horizon",
                        "text": "Simulated duration in hours."
                    },
                    {
                        "term": "Fidelity",
                        "text": "Explore (Δt = 0.01 h) for fast iteration, or Fidelity (Δt = 0.0005 h) for a fine, accurate trajectory. Set a Seed for reproducible measurement noise."
                    },
                    {
                        "term": "Controller flags",
                        "text": "Toggle composition control, override loops, and %G feedback (closed loop)."
                    },
                    {
                        "term": "Setpoints / MVs",
                        "text": "Edit closed-loop setpoints inline, or drag the open-loop MV sliders."
                    },
                    {
                        "term": "Disturbances (IDVs)",
                        "text": "Select one or more IDVs to inject, set a single Activation time (h), and give each a magnitude in the per-IDV fields that appear."
                    },
                    {
                        "term": "Plot panel",
                        "text": "Choose Variables to plot and toggle setpoint / limit overlays. The top graph shows measurements; the lower graph shows MVs."
                    }
                ]
            },
            {
                "type": "note",
                "text": "Save scenario / Load scenario at the bottom serialize the whole configuration to JSON so a run can be reproduced or shared."
            },
            {
                "type": "subheading",
                "text": "Simulate — Advanced panels"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Initial state",
                        "text": "Start from the mode default or paste a custom 50-element state vector (JSON list or comma/space separated). Load current mode's state seeds the editor."
                    },
                    {
                        "term": "Controller tuning",
                        "text": "An editable table of every PI gain, override limit, and setpoint ramp rate (default: the built-in Mode-1 PI tuning). Edit a cell to override it; Reset to defaults restores them."
                    },
                    {
                        "term": "Advanced solver",
                        "text": "Choose the integrator (RK4, Euler, RK45, RK23), the fixed step h, adaptive rtol/atol, and the record-every decimation."
                    }
                ]
            },
            {
                "type": "subheading",
                "text": "Dataset"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Export",
                        "text": "Tick which runs to include, pick CSV, Parquet, or JSON, and Build & download a tidy dataset."
                    },
                    {
                        "term": "Batch generation",
                        "text": "Run multiple seeds at once and optionally sweep one parameter (a setpoint field, horizon, control interval, or fixed step) across a list of values. The results table populates, and you can download the combined dataset or a metrics CSV."
                    }
                ]
            },
            {
                "type": "subheading",
                "text": "Compare"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "text": "Lists every run held in the session, with a table of their KPIs. Choose one or more Overlay variables to plot all runs together on a single graph. Copy all run IDs, or Clear all runs to reset the store."
                    }
                ]
            },
            {
                "type": "subheading",
                "text": "Metrics / Record"
            },
            {
                "type": "bullets",
                "items": [
                    {
                        "term": "Metrics",
                        "text": "Select a run to see its KPI panel (e.g. peak reactor pressure and other summary metrics); copy its run ID."
                    },
                    {
                        "term": "Experiment record",
                        "text": "View the full experiment record JSON inline and Download record JSON — a self-contained, reproducible description of the run."
                    }
                ]
            },
            {
                "type": "note",
                "text": "Background on the process itself lives on the separate About the TEP page, linked from the header."
            }
        ]
    }
}
