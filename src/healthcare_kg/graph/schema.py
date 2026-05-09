"""
Graph schema for the healthcare knowledge graph.

Node labels and their properties:
  :Diagnosis   — ICD-10-CM codes
  :LabTest     — LOINC codes
  :Drug        — RxNorm concepts
  :ClinicalConcept — SNOMED CT concepts

Relationship types:
  IS_A          — hierarchical parent-child within each ontology
  HAS_INGREDIENT — drug to active ingredient (RxNorm)
  MAPS_TO       — cross-ontology concept alignment (SNOMED → others)
  RELATED_TO    — general cross-ontology association
"""

CONSTRAINTS = [
    "CREATE CONSTRAINT diagnosis_code IF NOT EXISTS FOR (n:Diagnosis) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT labtest_loinc_num IF NOT EXISTS FOR (n:LabTest) REQUIRE n.loinc_num IS UNIQUE",
    "CREATE CONSTRAINT drug_rxcui IF NOT EXISTS FOR (n:Drug) REQUIRE n.rxcui IS UNIQUE",
    "CREATE CONSTRAINT concept_sctid IF NOT EXISTS FOR (n:ClinicalConcept) REQUIRE n.sctid IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX diagnosis_description IF NOT EXISTS FOR (n:Diagnosis) ON (n.description)",
    "CREATE INDEX labtest_name IF NOT EXISTS FOR (n:LabTest) ON (n.long_common_name)",
    "CREATE INDEX drug_name IF NOT EXISTS FOR (n:Drug) ON (n.name)",
    "CREATE INDEX concept_term IF NOT EXISTS FOR (n:ClinicalConcept) ON (n.preferred_term)",
]

SCHEMA_DESCRIPTION = """
Healthcare Knowledge Graph — Neo4j schema

NODE TYPES
----------
(:Diagnosis)
  code            STRING  — ICD-10-CM code (e.g. "E11.9")
  description     STRING  — human-readable description
  chapter         STRING  — ICD-10 chapter name
  billable        BOOLEAN — whether the code is a billable leaf code

(:LabTest)
  loinc_num       STRING  — LOINC code (e.g. "2339-0")
  long_common_name STRING — full display name
  component       STRING  — what is measured (e.g. "Glucose")
  property        STRING  — measurement property (e.g. "MCnc")
  scale           STRING  — scale type (e.g. "Qn", "Ord")
  class           STRING  — LOINC class (e.g. "CHEM", "HEM/BC")

(:Drug)
  rxcui           STRING  — RxNorm concept unique identifier
  name            STRING  — concept name
  tty             STRING  — term type: IN=ingredient, BN=brand, SCD=clinical drug, etc.

(:ClinicalConcept)
  sctid           STRING  — SNOMED CT concept identifier
  fsn             STRING  — fully specified name (includes semantic tag)
  preferred_term  STRING  — preferred clinical term
  semantic_tag    STRING  — e.g. "disorder", "finding", "procedure", "substance"

RELATIONSHIPS
-------------
(:Diagnosis)-[:IS_A]->(:Diagnosis)
(:LabTest)-[:IS_A]->(:LabTest)
(:Drug)-[:IS_A]->(:Drug)
(:Drug)-[:HAS_INGREDIENT]->(:Drug)
(:ClinicalConcept)-[:IS_A]->(:ClinicalConcept)
(:ClinicalConcept)-[:MAPS_TO {map_type}]->(:Diagnosis)
(:ClinicalConcept)-[:MAPS_TO {map_type}]->(:LabTest)
(:ClinicalConcept)-[:MAPS_TO {map_type}]->(:Drug)
(:Diagnosis)-[:RELATED_TO]->(:LabTest)
(:Diagnosis)-[:RELATED_TO]->(:Drug)
"""
