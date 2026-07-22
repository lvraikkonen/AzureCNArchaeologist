# Remove the Legacy sharedContent Field

Status: Accepted

Generated `contentGroup` objects contain only the CMS-confirmed `groupName`, `filterCriteriaJson`, `content`, `sortOrder`, and `isActive` fields. The current producer paths that emit legacy `sharedContent` and any compatibility validation for that field must be removed: genuinely global fragments move to `baseContent` or the appropriate `commonSections`, state-specific fragments become part of that group's `content`, and unreachable or ambiguous fragments remain validation evidence. Adding `sharedContent` back requires explicit CMS confirmation, a contract version change, and import regression evidence rather than a producer-side schema extension.
