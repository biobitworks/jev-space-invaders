# Zenodo operator checklist

Complete these values before publication:

- [ ] PREPRINT_LICENSE approved
- [ ] FCG_DATASET_LICENSE approved
- [ ] SOFTWARE_LICENSE approved (candidate Apache-2.0)
- [ ] PUBLICATION_DATE set to actual publication date
- [ ] COMMUNITY confirmed or omitted
- [ ] CONTRIBUTORS confirmed or none
- [ ] FUNDING/GRANTS confirmed or none
- [ ] RESERVE_DOI_BEFORE_FINAL_PDF = YES/NO
- [ ] CREATE_TWO_ZENODO_RECORDS = YES/NO
- [ ] `ZENODO_TOKEN` stored locally, never committed
- [ ] token has `deposit:write`; `deposit:actions` only if publishing
- [ ] final secret scan PASS
- [ ] final rights audit PASS
- [ ] final claim-path audit PASS
- [ ] final PDF visual audit PASS
- [ ] final SHA256 manifest PASS
- [ ] publication breakpoint independently verified
- [ ] publication MMR append, if performed, has ordered leaves + peaks/root + construction + verification receipt
- [ ] SIGNATURE_STATE remains NOT_SIGNED unless actual signing and verification occur
