# Use Maintained Desktop Controls for Defaults

Status: Accepted

For post-v0.4 extraction, a filter default comes from the maintained desktop control. The desktop control must declare one clear default, and its visible selected label must not contradict that default. If those conditions hold, missing, conflicting, or duplicate `selected` markers in the unmaintained mobile control are ignored. They do not change the payload and do not create a Source Quality Finding.

This rule does not ignore other differences. Desktop and mobile controls must still expose the same machine options and targets, and a desktop control that is missing a clear default still stops extraction. Mobile label differences continue to use the existing advisory finding.

This decision supersedes only the mobile-default reconciliation rule in ADR-0075. Desktop option order and labels remain authoritative, and no frozen Finding Code Policy is changed. Source HTML stays unchanged; the resolver applies the rule while reading it.
