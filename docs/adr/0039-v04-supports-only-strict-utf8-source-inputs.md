# v0.4 Supports Only Strict UTF-8 Source Inputs

Status: Accepted

v0.4 requires every Source Snapshot and its byte-identical Normalized Input to decode strictly as UTF-8 without replacement-character recovery; a UTF-8 BOM, when present, remains part of the immutable bytes. A missing or conflicting HTML charset declaration is a Source Quality Finding when strict decoding and reliable parsing still succeed, but illegal UTF-8 that prevents reliable reconstruction is a blocking Batch Item failure. Supporting legacy encodings or transcoding during normalization was rejected because the current source inventory declares UTF-8 and broader decoding would add ambiguity to fidelity evidence.
