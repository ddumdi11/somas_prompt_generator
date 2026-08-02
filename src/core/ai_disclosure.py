"""Zentrale KI-Kennzeichnung für alle SOMAS-Output-Formen (v0.14.0).

Eine Quelle der Wahrheit für die Transparenz-Kennzeichnung KI-generierter
Analysen, in drei Formen (Text / Markdown / HTML). Wird an drei Stellen
eingebunden — LinkedIn, Markdown-Export, WordPress —, jeweils am Fuß des
Beitrags. Alle drei Formen teilen denselben Kerntext (:data:`_CORE`), damit sie
nicht auseinanderdriften (Drift-Schutz per Konsistenztest, analog Modelllisten).

Rechtsgrundlage & Auffindbarkeit
--------------------------------
Art. 50 EU AI Act (Verordnung (EU) 2024/1689, Transparenzpflichten),
**anwendbar seit 2026-08-02**.

**Diese Kennzeichnung ist FREIWILLIG, keine Pflichterfüllung:** SOMAS-Beiträge
durchlaufen menschliche Prüfung, Quellenauswahl und redaktionelle Verantwortung
durch den Herausgeber und fallen damit unter die **Ausnahme nach Art. 50(4)**
(kein rein automatisiert veröffentlichter Inhalt). Der Herausgeber möchte die
Transparenz dennoch — als Standard, nicht als Option (daher kein GUI-Toggle).

EU-Icon (Basiszeichen „AI", für „KI beteiligt + eigene Textkennzeichnung"):
https://digital-strategy.ec.europa.eu/en/policies/eu-icons-labelling-ai-generated-content
Lizenz: frei nutzbar, keine Attribution nötig. Eingebunden per Hotlink
(PO-Entscheidung); bricht die EU-URL, bleibt die Textzeile bestehen.

Bei künftigen Regulierungs-Änderungen: ``grep "Art. 50"`` über das Projekt
findet dieses Modul UND jede Einbaustelle (einheitliches Kommentar-Tag
``# KI-Kennzeichnung (Art. 50 AI Act) — zentral in ai_disclosure.py``).
Geändert wird idealerweise nur dieses Modul.
"""

#: Label der Kennzeichnungszeile (in allen drei Formen identisch).
_LABEL = "KI-Kennzeichnung:"

#: Kerntext — die EINE Quelle der Wahrheit. Kommt in allen drei Formen wörtlich
#: vor; der Konsistenztest wacht darüber.
_CORE = (
    "Analyse KI-generiert · Idee, Quellenauswahl & Kuration: Mensch · "
    "Veröffentlichung nach menschlicher Prüfung."
)

#: Basis-URL des EU-Icons (Basiszeichen „AI", schwarz, 3x2). Hotlink.
AI_DISCLOSURE_ICON_URL = (
    "https://digital-strategy.ec.europa.eu/sites/default/files/2026-06/"
    "AI%20LABELS_3x2_AI_black.png"
)

#: Alt-Text des Icons (Barrierefreiheits-Empfehlung der EU).
AI_DISCLOSURE_ICON_ALT = "EU-KI-Kennzeichen: KI-generierter Inhalt"

#: Reiner Text (für LinkedIn — kein Icon, keine URL, nur die Zeile).
AI_DISCLOSURE_TEXT = f"{_LABEL} {_CORE}"

#: Markdown (für den Markdown-Export). Markdown kann keine Bildgröße setzen,
#: daher das EU-Icon als HTML-``<img>`` (width), darunter die Textzeile mit
#: fett gesetztem Label.
AI_DISCLOSURE_MARKDOWN = (
    f'<img src="{AI_DISCLOSURE_ICON_URL}" alt="{AI_DISCLOSURE_ICON_ALT}" '
    f'width="90">\n\n'
    f"**{_LABEL}** {_CORE}"
)

#: HTML (für WordPress). Ein ``<p>``-Block mit Inline-Icon (vertikal zentriert)
#: und fett gesetztem Label.
AI_DISCLOSURE_HTML = (
    f'<p><img src="{AI_DISCLOSURE_ICON_URL}" alt="{AI_DISCLOSURE_ICON_ALT}" '
    f'width="90" style="vertical-align: middle; margin-right: 8px;">'
    f"<strong>{_LABEL}</strong> {_CORE}</p>"
)
