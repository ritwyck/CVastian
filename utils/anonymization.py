"""Anonymization utilities for CVButler."""

import re
# import spacy  # Temporarily disabled for testing
from typing import List, Tuple


class Anonymizer:
    """Class for anonymizing text content."""

    def __init__(self):
        """Initialize with spaCy model."""
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Download if not available
            print("Downloading spaCy model...")
            import subprocess
            subprocess.run(
                ["python", "-m", "spacy", "download", "en_core_web_sm"])
            self.nlp = spacy.load("en_core_web_sm")

        # PII patterns
        self.pii_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b(\+?\d{1,3}[-.\s]?)?\(?[\d\s\-\(\)]{3,}\)?[\d\s\-\(\)]{3,}[\d\s\-\(\)]{3,}\b',
            'address': r'\b\d+\s+[A-Za-z0-9,\s]+(?:\s+St|\s+Ave|\s+Rd|\s+Dr|\s+Ln|\s+Ct|\s+Pl|\s+Blvd|\s+Way|\s+Ter|\s+Ln|\s+Plaza)+(?:\s+\w{2}\s+\d{5})?\b',
            'url': r'\bhttps?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=_.%-])*)?(?:\#(?:\w\.])*)?)?\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'date': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b'
        }

        # Bias indicators
        self.bias_indicators = [
            'male', 'female', 'man', 'woman', 'boy', 'girl',
            'age', 'aged', 'years old', 'born in', 'graduate', 'graduation',
            'race', 'ethnicity', 'religion', 'sexual orientation',
            'marital status', 'parent', 'dependents'
        ]

    def anonymize_pii(self, text: str) -> Tuple[str, List[str]]:
        """Remove personally identifiable information."""
        redacted_parts = []

        # Apply regex patterns
        for category, pattern in self.pii_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                text = text.replace(match, f"[REDACTED_{category.upper()}]")
                redacted_parts.append((category, match))

        # NER for names, organizations, etc.
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in ['PERSON', 'ORG', 'GPE', 'LOC']:
                placeholder = f"[REDACTED_{ent.label_}]"
                text = text.replace(ent.text, placeholder)
                redacted_parts.append((ent.label_, ent.text))

        return text, redacted_parts

    def remove_bias_indicators(self, text: str) -> Tuple[str, List[str]]:
        """Remove bias indicators."""
        removed_parts = []
        text_lower = text.lower()

        for indicator in self.bias_indicators:
            if indicator in text_lower:
                # Simple removal - can be improved
                pattern = r'\b' + re.escape(indicator) + r'\b'
                if re.search(pattern, text, re.IGNORECASE):
                    text = re.sub(
                        pattern, '[BIASE> INDICATOR]', text, flags=re.IGNORECASE)
                    removed_parts.append(indicator)

        return text, removed_parts

    def anonymize(self, text: str) -> Tuple[str, dict]:
        """Full anonymization pipeline."""
        # First, anonymize PII
        pii_removed, pii_parts = self.anonymize_pii(text)

        # Then remove bias indicators
        bias_removed, bias_parts = self.remove_bias_indicators(pii_removed)

        # Create audit log
        audit = {
            'pii_redacted': len(pii_parts),
            'bias_indicators_removed': len(bias_parts),
            'pii_details': pii_parts,
            'bias_details': bias_parts
        }

        return bias_removed, audit


def anonymize_text(text: str) -> Tuple[str, dict]:
    """Convenience function for anonymization."""
    # Temporarily disabled spacy for testing
    return text, {"pii_redacted": 0, "bias_indicators_removed": 0, "pii_details": [], "bias_details": []}
    # anonymizer = Anonymizer()
    # return anonymizer.anonymize(text)
