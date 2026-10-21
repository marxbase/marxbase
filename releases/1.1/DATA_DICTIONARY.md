# MarxBase data dictionary (release 1.1)

Counting rule: a multi-gene combination repeats the same value on each member row. Count `finding_id`, not rows, in summaries.

Licence note: data CC BY 4.0, code MIT. Evidence sentences are third-party text from abstracts and are NOT covered by the data licence.

## results.csv

| column | meaning |
| --- | --- |
| public_id | Stable result ID (MARXBASE-R000123); never reused. |
| finding_id | Groups the rows of one multi-gene combination (count findings, not rows, in summaries). |
| n_members | Number of rows in the finding (1 for a single-gene result). |
| pmid | PubMed ID of the paper. |
| gene_id | Stable gene ID (MARXBASE-G000123). |
| gene_name | Gene name used in the database. |
| reported_gene_name | The name the paper used, when it differs (for example after a merge). |
| gene_organism | Species the gene comes from. |
| gene_kind | locus_tagged | scerevisiae_gene | undetermined_paralog | enzyme_or_protein_label | heterologous_gene | unmapped_name. |
| locus_tag | K. marxianus (KLMA_) or S. cerevisiae systematic ID, when assigned. |
| intervention_type | What was done to the gene (deletion, overexpression, ...). |
| effect_direction | increases | decreases | no_effect | mixed. |
| result_class | positive | negative | context-dependent (relative to the intended effect). |
| phenotype | What was measured. |
| phenotype_category | One of the 10 phenotype categories. |
| effect_magnitude_text | The size of the effect exactly as written in the abstract, when stated. |
| metric_type | titer, yield, productivity, specific_rate, conversion, activity, fold_change or other. |
| new_value | Quantified value after the change (number; unit in value_unit). |
| baseline_value | Quantified comparison value (number). |
| value_unit | Unit exactly as written. |
| value_qualifier | exact | approx | greater_than | less_than. |
| percent_change | Percent change as stated (unsigned; the direction is effect_direction). |
| fold_change | Fold change as stated. |
| comparator | What the value is compared with, as written. |
| statistics_reported | significant | not_significant, when the abstract says so. |
| n_replicates | Number of replicates, when stated. |
| product | Product (24-term list), when the result concerns a product. |
| product_class | One of 8 product classes. |
| host_organism | Species the change was made in. |
| strain_id | Stable strain ID (MARXBASE-S000123), when a strain is recorded. |
| strain_name | Strain as recorded. |
| condition_label | Short tag separating rows of the same gene and phenotype under different conditions. |
| temperature_c | Culture temperature in degrees C, when a single value was stated. |
| temperature_note | Temperature as text when it is a range or threshold. |
| ph | pH, when stated. |
| scale | microplate | shake_flask | bench_bioreactor | pilot | industrial. |
| volume_l | Culture volume in litres, when stated. |
| process_mode | batch | fed_batch | continuous | SSF | SSCF | CBP. |
| carbon_source | Carbon source as written. |
| feedstock_medium | Medium or feedstock as written. |
| oxygen_level | aerobic | microaerobic | anaerobic. |
| cultivation_time_h | Cultivation time in hours, when stated. |
| stressor_type | Stressor, when the result concerns tolerance. |
| stressor_level | Stressor level as written. |
| combined_with | Other changes made together with this one (a combination). |
| evidence_sentence | Short quotation from the abstract supporting the result (plain text); see the licence note. |
| evidence_sentence_html | Same sentence with <i>, <sub>, <sup> kept; safe to insert in a web page. |
| evidence_source | Where the evidence sentence comes from (abstract). |
| provenance | hand-curated (gold) | hand-curated, edited after curator review | curator-added | AI-extracted, curator-verified. |
| provenance_note | Why a field is empty (for example no extracted evidence sentence). |
| year | Publication year. |

## genes.csv

| column | meaning |
| --- | --- |
| gene_id | Stable gene ID. |
| gene_name | Gene name used in the database. |
| organism | Species the gene comes from. |
| gene_kind | See results.gene_kind. |
| locus_tag | Systematic ID, when assigned. |
| id_method | How the identity was assigned (name_match, reciprocal_best_hit, manual). |
| id_confidence | high | medium (| manual decisions are high). |
| identity_note | Curator note on the identity decision. |
| n_results | Number of public results for this gene. |

## gene_orthologs.csv

| column | meaning |
| --- | --- |
| gene_id | Stable gene ID. |
| ortholog_organism | Species of the ortholog. |
| ortholog_systematic_id | Systematic ID of the ortholog. |
| ortholog_gene_name | Name of the ortholog. |
| method | How it was found (reciprocal_best_hit). |
| identity_pct | Percent identity. |
| coverage_pct | Percent coverage. |
| rank | 1 = best; 2 and up = co-orthologs. |
| confidence | high | medium | low. |

## gene_aliases.csv

| column | meaning |
| --- | --- |
| gene_id | Stable gene ID. |
| alias_name | Other name of the gene. |
| alias_type | merged_duplicate | synonym | reported_name. |

## gene_candidate_loci.csv

| column | meaning |
| --- | --- |
| gene_id | Stable gene ID. |
| locus_tag | Candidate K. marxianus locus. |
| status | candidate (undetermined paralog) | confirmed | rejected. |
| product | Annotated product of the locus. |
| hint | Why this locus is a candidate. |

## strains.csv

| column | meaning |
| --- | --- |
| strain_id | Stable strain ID. |
| strain_name | Strain as recorded. |
| species | Species, when stated. |
| parent_strain_id | Stable ID of the parent strain, when recorded. |
| parent_strain_name | Name of the parent strain. |
| n_results | Number of public results in this strain. |

## strain_aliases.csv

| column | meaning |
| --- | --- |
| strain_id | Stable strain ID. |
| alias | Other designation (collection numbers, spellings). |
| alias_type | collection_id | lab_name | spelling_variant. |

## citations.csv

| column | meaning |
| --- | --- |
| pmid | PubMed ID. |
| doi | DOI. |
| title | Title (plain text). |
| title_html | Title with <i>, <sub>, <sup> kept. |
| authors | Authors as 'Family Initials; ...'. |
| journal | Journal. |
| year | Year. |
| pmcid | PubMed Central ID, when one exists. |
| first_author | First author. |
| last_author | Last author. |
| last_author_affiliation | Affiliation of the last author (e-mail addresses removed). |
| country | Country of the last author's affiliation. |
| publication_type | PubMed publication type. |
| n_results | Number of public results from this paper (0 = the abstract was text-mined but no finding was extracted). |

## products.csv

| column | meaning |
| --- | --- |
| product_id | Internal product number (stable within a release). |
| product_name | Product. |
| product_class | Product class. |

## comparisons.csv

| column | meaning |
| --- | --- |
| public_id | Stable ID of the result. |
| other_organism | Yeast the authors compare with. |
| relation | same_as | weaker_than | stronger_than | different | opposite | not_conserved. |
| evidence_sentence | The authors' sentence (plain text). |
| evidence_sentence_html | Same sentence with <i>, <sub>, <sup> kept. |
