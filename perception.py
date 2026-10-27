import numpy as np

class PerceptionModule:
    def __init__(self, sensor_range=6, noise_probability=0.12):
        self.sensor_range = sensor_range
        self.noise_probability = noise_probability

    def scan_environment(self, agent_pos, environment):
        """
        Simulates local sensor readings around the agent.
        Introduces smoke/haze occlusion and telemetry noise.
        """
        ax, ay = agent_pos
        width, height = environment.width, environment.height
        
        local_perception = {}
        
        for y in range(max(0, ay - self.sensor_range), min(height, ay + self.sensor_range + 1)):
            for x in range(max(0, ax - self.sensor_range), min(width, ax + self.sensor_range + 1)):
                # Chebyshev distance (grid steps)
                dist = max(abs(x - ax), abs(y - ay))
                if dist <= self.sensor_range:
                    true_state = environment.grid[y, x]
                    perceived_state = self._apply_sensor_noise(true_state)
                    
                    local_perception[(x, y)] = {
                        'perceived_state': perceived_state,
                        'distance': dist,
                        'is_burning': (perceived_state == 3)
                    }
                    
        # Scan for survivors within sensor range
        detected_survivors = []
        for s in environment.survivors:
            sx, sy = s['pos']
            dist = max(abs(sx - ax), abs(sy - ay))
            if dist <= self.sensor_range and not s['rescued']:
                detected_survivors.append({
                    'id': s['id'],
                    'pos': (sx, sy),
                    'injury_severity': s['injury_severity'],
                    'distance': dist
                })
                
        return local_perception, detected_survivors

    def _apply_sensor_noise(self, true_state):
        """Introduces stochastic uncertainty mimicking heavy smoke haze."""
        if np.random.rand() < self.noise_probability:
            # Smoke can blur open ground (0) and dense brush (1)
            if true_state == 0:
                return 1
            elif true_state == 1:
                return 0
        return true_state