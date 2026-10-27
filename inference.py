class InferenceEngine:
    def __init__(self):
        pass

    def evaluate_priorities(self, detected_survivors, local_perception, agent_pos):
        """
        Applies symbolic rules (forward-chaining) to rank survivors 
        by rescue priority based on danger and medical urgency.
        """
        scored_targets = []

        for survivor in detected_survivors:
            sx, sy = survivor['pos']
            severity = survivor['injury_severity']
            
            # Base priority score from injury severity
            if severity == 'Critical':
                urgency_score = 100
            elif severity == 'Moderate':
                urgency_score = 60
            else:
                urgency_score = 30
                
            # Environmental hazard modifier: Check proximity to fire in local perception
            fire_proximity_penalty = 0
            for (px, py), data in local_perception.items():
                if data['is_burning']:
                    dist_to_fire = max(abs(px - sx), abs(py - sy))
                    if dist_to_fire <= 2:  # Fire is dangerously close to survivor
                        fire_proximity_penalty += 40

            # Distance modifier (closer is preferred if urgencies are tied)
            distance_penalty = survivor['distance'] * 2
            
            # Final calculated priority (higher score = rescue first)
            final_priority = urgency_score - fire_proximity_penalty - distance_penalty
            
            scored_targets.append({
                'id': survivor['id'],
                'pos': (sx, sy),
                'priority_score': final_priority,
                'urgency': severity,
                'fire_threat': fire_proximity_penalty > 0
            })

        # Sort targets descending by priority score
        scored_targets.sort(key=lambda t: t['priority_score'], reverse=True)
        return scored_targets