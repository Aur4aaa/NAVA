"""Original, concise planning summaries; not licensed ISO normative text.

The target edition was requested by the product brief. Live official-source
verification was blocked by the execution environment on 2026-10-20. Treat this
catalog as unverified until an authorized maintainer checks the official sources.
Changes must use a NEW release key so existing organizational snapshots survive.
"""

CATALOG_RELEASE = 'nava-iso27001-2022-amd1-2024-r1'
FRAMEWORK_NAME = 'ISO/IEC 27001'
FRAMEWORK_EDITION = '2022 + Amendment 1:2024'
VERIFIED = False
VERIFICATION_DATE = None
VERIFICATION_ATTEMPT_DATE = '2026-10-20'
PROVENANCE = (
    'Original NAVA planning summaries, not ISO normative wording. '
    'Identifiers and target edition require verification against licensed material. '
    'Official HTTPS source checks attempted on 2026-10-20 returned proxy HTTP 403. '
    'No assertion of current edition, official wording, compliance, or certification.'
)
SOURCES = [
    {'title': 'ISO/IEC 27001 official overview and edition listing',
     'url': 'https://www.iso.org/standard/27001',
     'role': 'Official requirements edition verification',
     'status': 'unverified: HTTP 403 blocked retrieval'},
    {'title': 'ISO/IEC 27001:2022/Amd 1:2024 catalog locator',
     'url': 'https://www.iso.org/standard/88435.html',
     'role': 'Official amendment verification; locator not verified in this environment',
     'status': 'unverified: HTTP 403 blocked retrieval'},
    {'title': 'ISO/IEC 27002:2022 catalog locator',
     'url': 'https://www.iso.org/standard/75652.html',
     'role': 'Implementation guidance, not certification requirements; locator unverified',
     'status': 'unverified: destination blocked; this URL not retrieved'},
]

# These are mandatory management-system areas, not optional Annex A controls.
CLAUSES = [
    ('4', 'Organization and context',
     'Understand relevant internal and external issues, interested-party needs, ISMS boundaries, and the management system. Record whether climate change is relevant and relevant climate-related party requirements, with rationale.'),
    ('5', 'Leadership and accountability',
     'Record leadership commitments, information-security policy, responsibilities, and decision authority.'),
    ('6', 'Planning and objectives',
     'Plan responses to risks and opportunities, define assessment and treatment approaches, set measurable objectives, and plan ISMS changes.'),
    ('7', 'Resources and support',
     'Provide resources, competence, awareness, communications, and controlled information needed for the ISMS.'),
    ('8', 'Operational execution',
     'Operate the planned processes, reassess information-security risks, and carry out risk treatment with retained records.'),
    ('9', 'Performance and review',
     'Evaluate security and ISMS performance through monitoring, internal audit, and management review.'),
    ('10', 'Correction and improvement',
     'Address nonconformities and their causes, evaluate corrective-action effectiveness, and improve the ISMS over time.'),
]

# (identifier, original short label, original practical summary). Labels are
# intentionally concise and may differ from the official standard's headings.
THEMES = {
    'organizational': ('Organizational', [
        ('A.5.1', 'Security policy direction', 'Set, approve, communicate, and periodically review the organization’s security policy direction.'),
        ('A.5.2', 'Security responsibilities', 'Assign information-security responsibilities and the authority needed to carry them out.'),
        ('A.5.3', 'Separation of duties', 'Split conflicting responsibilities to reduce errors and misuse of authority.'),
        ('A.5.4', 'Management accountability', 'Require managers to support and enforce security responsibilities in their teams.'),
        ('A.5.5', 'Authority contacts', 'Maintain appropriate contacts with relevant authorities for security matters.'),
        ('A.5.6', 'Professional security contacts', 'Maintain relevant security community or specialist contacts to improve awareness and response.'),
        ('A.5.7', 'Threat understanding', 'Collect and assess threat information so it can inform protective actions.'),
        ('A.5.8', 'Security within projects', 'Include security needs and risk decisions in project planning and delivery.'),
        ('A.5.9', 'Information and asset inventory', 'Maintain an inventory of information and related assets with clear ownership.'),
        ('A.5.10', 'Acceptable handling and use', 'Define and communicate acceptable use and handling rules for information and related assets.'),
        ('A.5.11', 'Asset return', 'Recover organizational assets when employment, contracts, or responsibilities change or end.'),
        ('A.5.12', 'Information classification', 'Classify information according to confidentiality, integrity, availability, and stakeholder needs.'),
        ('A.5.13', 'Classification labels', 'Use suitable labels and handling cues consistent with information classifications.'),
        ('A.5.14', 'Information transfer safeguards', 'Protect information transfers with agreed rules and suitable safeguards.'),
        ('A.5.15', 'Access rules', 'Define access restrictions that reflect business and information-security needs.'),
        ('A.5.16', 'Identity lifecycle', 'Manage identities throughout creation, change, use, and removal.'),
        ('A.5.17', 'Authentication information', 'Protect credentials and guide users in handling authentication information safely.'),
        ('A.5.18', 'Access rights lifecycle', 'Authorize, review, adjust, and remove access rights as responsibilities change.'),
        ('A.5.19', 'Supplier security relationships', 'Identify and manage security risks associated with supplier relationships.'),
        ('A.5.20', 'Security in supplier agreements', 'Agree and record appropriate security requirements with suppliers.'),
        ('A.5.21', 'Technology supply-chain risk', 'Manage information-security risks in ICT products, services, and their supply chains.'),
        ('A.5.22', 'Supplier service assurance', 'Monitor supplier security performance and assess changes to supplied services.'),
        ('A.5.23', 'Cloud service security', 'Define security responsibilities and controls for selecting, using, changing, and exiting cloud services.'),
        ('A.5.24', 'Incident response preparation', 'Prepare incident-management roles, processes, communications, and response capabilities.'),
        ('A.5.25', 'Security event assessment', 'Assess security events consistently and decide when they constitute incidents.'),
        ('A.5.26', 'Incident handling', 'Respond to information-security incidents using established procedures.'),
        ('A.5.27', 'Learning from incidents', 'Use incident knowledge to improve security measures and future response.'),
        ('A.5.28', 'Evidence handling', 'Identify, collect, acquire, and preserve incident evidence appropriately for its intended use.'),
        ('A.5.29', 'Security during disruption', 'Maintain appropriate information-security safeguards during disruption.'),
        ('A.5.30', 'ICT continuity readiness', 'Prepare and test ICT capabilities against business-continuity needs.'),
        ('A.5.31', 'Relevant obligations', 'Identify and maintain applicable legal, regulatory, statutory, and contractual security obligations.'),
        ('A.5.32', 'Intellectual property', 'Protect intellectual property and comply with related rights and obligations.'),
        ('A.5.33', 'Record protection', 'Protect records against loss, alteration, unauthorized access, and inappropriate disclosure.'),
        ('A.5.34', 'Privacy and personal information', 'Meet applicable privacy and personal-information protection needs.'),
        ('A.5.35', 'Independent security review', 'Arrange suitable independent reviews of the organization’s approach to security and its implementation.'),
        ('A.5.36', 'Security rule compliance', 'Review compliance with the organization’s security policies, rules, and standards.'),
        ('A.5.37', 'Operating instructions', 'Document necessary operating procedures and make them available to the people who need them.'),
    ]),
    'people': ('People', [
        ('A.6.1', 'Personnel screening', 'Conduct proportionate background checks consistent with applicable obligations and role risks.'),
        ('A.6.2', 'Employment security terms', 'Define security responsibilities within employment or engagement terms.'),
        ('A.6.3', 'Security learning', 'Provide role-appropriate security awareness, education, training, and updates.'),
        ('A.6.4', 'Disciplinary handling', 'Establish and communicate a fair process for handling security-policy violations.'),
        ('A.6.5', 'Responsibilities after role changes', 'Define security obligations that remain after employment ends or responsibilities change.'),
        ('A.6.6', 'Confidentiality commitments', 'Identify, maintain, and review appropriate confidentiality or nondisclosure commitments.'),
        ('A.6.7', 'Remote working safeguards', 'Protect information accessed, processed, or stored while working remotely.'),
        ('A.6.8', 'Security event reporting', 'Make prompt reporting of suspected security events clear and accessible to personnel.'),
    ]),
    'physical': ('Physical', [
        ('A.7.1', 'Security boundaries', 'Establish physical boundaries appropriate to the information and assets being protected.'),
        ('A.7.2', 'Physical entry controls', 'Restrict and manage entry to protected locations and spaces.'),
        ('A.7.3', 'Protected workspaces', 'Design physical security for offices, rooms, and facilities according to risk.'),
        ('A.7.4', 'Physical security monitoring', 'Monitor premises for unauthorized physical access where appropriate.'),
        ('A.7.5', 'Environmental threat protection', 'Protect against physical and environmental threats to information and related assets.'),
        ('A.7.6', 'Work in secure areas', 'Define safeguards for people and activities within secure areas.'),
        ('A.7.7', 'Clear work surfaces and screens', 'Reduce exposure of sensitive information on desks, screens, and other work surfaces.'),
        ('A.7.8', 'Equipment placement', 'Place and protect equipment to limit physical and environmental exposure.'),
        ('A.7.9', 'Assets outside premises', 'Protect equipment and other assets used away from organizational premises.'),
        ('A.7.10', 'Storage-media lifecycle', 'Manage storage media through use, transport, retention, and disposal.'),
        ('A.7.11', 'Supporting utilities', 'Protect information-processing facilities against failure of supporting utilities.'),
        ('A.7.12', 'Cable protection', 'Protect power and communications cabling against damage, interference, and interception.'),
        ('A.7.13', 'Equipment servicing', 'Maintain equipment so it remains available and preserves information security.'),
        ('A.7.14', 'Safe disposal and reuse', 'Remove or securely erase sensitive information before equipment is disposed of or reused.'),
    ]),
    'technological': ('Technological', [
        ('A.8.1', 'Endpoint safeguards', 'Protect information accessible through or stored on user endpoint devices.'),
        ('A.8.2', 'Privileged access', 'Restrict, authorize, and manage privileged access rights.'),
        ('A.8.3', 'Information access limits', 'Restrict access to information and application functions according to access policy.'),
        ('A.8.4', 'Source-code access', 'Control access to source code, development tools, and related repositories.'),
        ('A.8.5', 'Secure authentication', 'Use authentication methods appropriate to access restrictions and risk.'),
        ('A.8.6', 'Capacity planning', 'Monitor and manage resources against current and expected capacity needs.'),
        ('A.8.7', 'Malware protection', 'Combine protective technology and user awareness to reduce malware risk.'),
        ('A.8.8', 'Technical vulnerability response', 'Identify relevant technical vulnerabilities and take proportionate action on exposure.'),
        ('A.8.9', 'Secure configurations', 'Establish, document, monitor, and review secure configurations.'),
        ('A.8.10', 'Information deletion', 'Delete information when it is no longer needed, subject to retention requirements.'),
        ('A.8.11', 'Data masking', 'Use suitable masking techniques to limit unnecessary exposure of sensitive data.'),
        ('A.8.12', 'Data leakage prevention', 'Apply measures to detect or prevent inappropriate disclosure of sensitive information.'),
        ('A.8.13', 'Backup protection and testing', 'Maintain and test backups of information, software, and systems according to agreed needs.'),
        ('A.8.14', 'Processing redundancy', 'Provide redundancy appropriate to availability requirements.'),
        ('A.8.15', 'Event logging', 'Produce, protect, retain, and analyze useful event logs.'),
        ('A.8.16', 'Activity monitoring', 'Monitor systems and networks for unusual activity and assess possible incidents.'),
        ('A.8.17', 'Time synchronization', 'Synchronize relevant system clocks to suitable reference time sources.'),
        ('A.8.18', 'Powerful utility programs', 'Restrict and control utilities that can bypass normal security controls.'),
        ('A.8.19', 'Operational software installation', 'Manage software installation on operational systems through suitable controls.'),
        ('A.8.20', 'Network safeguards', 'Protect networks and network devices against relevant security threats.'),
        ('A.8.21', 'Network service security', 'Specify and monitor security requirements for network services.'),
        ('A.8.22', 'Network separation', 'Separate networks, systems, and users where risk and access requirements call for it.'),
        ('A.8.23', 'Web access filtering', 'Manage access to external websites to reduce exposure to malicious or inappropriate content.'),
        ('A.8.24', 'Cryptographic protection', 'Define and use appropriate cryptography, including the management of cryptographic keys.'),
        ('A.8.25', 'Secure development lifecycle', 'Integrate security rules and practices throughout software and system development.'),
        ('A.8.26', 'Application security needs', 'Identify and approve security requirements when developing or acquiring applications.'),
        ('A.8.27', 'Secure engineering principles', 'Apply and maintain security engineering principles in system design and change.'),
        ('A.8.28', 'Secure coding practices', 'Use coding practices that address relevant software vulnerabilities.'),
        ('A.8.29', 'Development security testing', 'Perform appropriate security testing during development and acceptance.'),
        ('A.8.30', 'Outsourced development assurance', 'Direct, monitor, and review outsourced development according to security needs.'),
        ('A.8.31', 'Environment separation', 'Separate development, testing, and production environments to reduce exposure.'),
        ('A.8.32', 'Controlled changes', 'Subject changes to systems and processing facilities to suitable control procedures.'),
        ('A.8.33', 'Test information protection', 'Select and protect information used for testing appropriately.'),
        ('A.8.34', 'Protection during audit testing', 'Plan and agree audit-related testing to limit harm to operational systems.'),
    ]),
}
CONTROLS = [
    {'identifier': identifier, 'title': title, 'summary': summary, 'theme': theme}
    for theme, (_, controls) in THEMES.items()
    for identifier, title, summary in controls
]
