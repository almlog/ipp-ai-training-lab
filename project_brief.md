# My agent: hitman (HITMAN)
Project: IPP AI Training Lab (IPP 社内AIアプリ開発実践研修)
Author: Shunpei Suzuki <suzuki.shunpei@ipp.local> (IPP)
Copyright: Copyright (c) 2026 Shunpei Suzuki (IPP). All rights reserved.
Reference: Built with reference to Google Cloud's "Build with Gemini World Tour (Track 3)" concepts, restructured and implemented as an original enterprise AI agent cockpit and training lab by Shunpei Suzuki for IPP
One-liner: A conversational agent named HITMAN that helps operators execute rigid legacy Excel SOPs step-by-step with interactive checklist cards and automated validation tools.

Tool coverage:
- Memory: Current step progress, operator experience level, target environment (staging/production), and session checklist state.
- Tools: Procedure step retrieval (`get_procedure_step`), command parameter generator (`generate_step_command`), and execution log validation (`verify_step_output`).
- Catalog/UI: Step instruction cards (objective, executable command, warning badges) and procedure progress dashboard table.
- Image gen: n/a
- Sandbox: Parameter substitution calculation and log validation logic.

Core rails (everyone): memory, tools, eval, deploy, frontend
My stretch menu (pick later): storage + A2UI, code sandbox, evaluation
First eval question: Excel手順書のステップ2を開始してください。対象環境はステージングです。
