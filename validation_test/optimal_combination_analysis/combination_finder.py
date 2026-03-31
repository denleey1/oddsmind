from typing import List, Dict, Set, Tuple, Any

class CombinationFinder:
    """
    Implements the Greedy Complementary algorithm to find the optimal combination of companies.
    """

    def find_best_combination(self, 
                            matches: List[Any], 
                            predictions: Dict[Any, Dict[Any, bool]], 
                            k: int = 5) -> Dict[str, Any]:
        """
        Finds the top K companies that complement each other to maximize coverage.

        Args:
            matches: List of match IDs.
            predictions: Dictionary mapping match_id -> { company_id: is_correct (bool) }.
            k: Number of companies to select.

        Returns:
            Dictionary containing:
                - selected_companies: List of selected company IDs.
                - total_matches: Total number of matches analyzed.
                - covered_matches: Number of matches covered by the combination.
                - coverage_rate: Percentage of matches covered.
                - details: List of dictionaries with step-by-step selection details.
        """
        
        # 1. Build Coverage Matrix: match_id -> Set[company_id] (companies that got it right)
        match_correct_companies_map: Dict[Any, Set[Any]] = {}
        all_companies: Set[Any] = set()
        
        for match_id in matches:
            match_correct_companies_map[match_id] = set()
            if match_id in predictions:
                for company_id, is_correct in predictions[match_id].items():
                    all_companies.add(company_id)
                    if is_correct:
                        match_correct_companies_map[match_id].add(company_id)

        # Pre-calculate overall accuracy for tie-breaking
        # accuracy = correct_count / total_matches_participated
        company_stats = {}
        for company_id in all_companies:
            correct_count = 0
            participation_count = 0
            for match_id in matches:
                if match_id in predictions and company_id in predictions[match_id]:
                    participation_count += 1
                    if predictions[match_id][company_id]:
                        correct_count += 1
            
            accuracy = correct_count / participation_count if participation_count > 0 else 0
            company_stats[company_id] = {
                'accuracy': accuracy,
                'correct_count': correct_count
            }

        # 2. Initialization
        uncovered_matches: Set[Any] = set(matches)
        selected_companies: List[Any] = []
        selection_details: List[Dict] = []
        
        candidate_companies = list(all_companies)

        # 3. Greedy Iteration
        for i in range(k):
            if not uncovered_matches:
                break
                
            best_company = None
            best_gain = -1
            
            # Find the company with the highest marginal gain
            for company_id in candidate_companies:
                if company_id in selected_companies:
                    continue
                
                # Calculate Gain: count of matches in uncovered_matches that this company predicted correctly
                gain = 0
                for match_id in uncovered_matches:
                    if company_id in match_correct_companies_map.get(match_id, set()):
                        gain += 1
                
                # Selection logic with tie-breaking
                if gain > best_gain:
                    best_gain = gain
                    best_company = company_id
                elif gain == best_gain:
                    if best_company is None:
                        best_company = company_id
                    else:
                        # Tie-breaker: choose company with higher overall accuracy
                        curr_acc = company_stats[company_id]['accuracy']
                        best_acc = company_stats[best_company]['accuracy']
                        if curr_acc > best_acc:
                            best_company = company_id
            
            if best_company is not None and best_gain > 0:
                selected_companies.append(best_company)
                
                # Identify newly covered matches
                newly_covered = []
                for match_id in list(uncovered_matches): # iterate copy
                    if best_company in match_correct_companies_map.get(match_id, set()):
                        uncovered_matches.remove(match_id)
                        newly_covered.append(match_id)
                
                selection_details.append({
                    'step': i + 1,
                    'company_id': best_company,
                    'marginal_gain': best_gain,
                    'total_accuracy': company_stats[best_company]['accuracy'],
                    'newly_covered_matches': len(newly_covered) # Store count to keep it light
                })
            else:
                # No remaining company adds value
                break

        total_matches = len(matches)
        covered_count = total_matches - len(uncovered_matches)
        coverage_rate = (covered_count / total_matches) * 100 if total_matches > 0 else 0

        return {
            'selected_companies': selected_companies,
            'total_matches': total_matches,
            'covered_matches': covered_count,
            'coverage_rate': round(coverage_rate, 2),
            'details': selection_details
        }
