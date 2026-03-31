from typing import List, Dict, Set, Any

class CoverageAnalyzer:
    """
    Analyzes the coverage of a specific set of companies.
    """
    
    def analyze_coverage(self, 
                         matches: List[Any], 
                         predictions: Dict[Any, Dict[Any, bool]], 
                         selected_companies: List[Any]) -> Dict[str, Any]:
        """
        Calculates how many matches are covered by the selected companies.
        
        Args:
            matches: List of match IDs.
            predictions: Dictionary mapping match_id -> { company_id: is_correct (bool) }.
            selected_companies: List of company IDs to analyze.
            
        Returns:
            Dictionary with coverage statistics.
        """
        covered_matches = set()
        details_per_match = {}
        
        for match_id in matches:
            is_covered = False
            correct_companies = []
            
            if match_id in predictions:
                for company_id in selected_companies:
                    if company_id in predictions[match_id] and predictions[match_id][company_id]:
                        is_covered = True
                        correct_companies.append(company_id)
            
            if is_covered:
                covered_matches.add(match_id)
            
            details_per_match[match_id] = {
                'is_covered': is_covered,
                'correct_companies': correct_companies
            }
            
        total = len(matches)
        covered_count = len(covered_matches)
        coverage_rate = (covered_count / total) * 100 if total > 0 else 0
        
        return {
            'total_matches': total,
            'covered_matches': covered_count,
            'coverage_rate': round(coverage_rate, 2),
            'uncovered_matches': list(set(matches) - covered_matches),
            'match_details': details_per_match
        }
