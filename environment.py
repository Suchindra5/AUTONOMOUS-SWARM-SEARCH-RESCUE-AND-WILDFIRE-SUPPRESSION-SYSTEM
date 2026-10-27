import numpy as np

class Environment:
    def __init__(self, width=30, height=30):
        self.width = width
        self.height = height
        
        # Grid state representations:
        # 0: Open Ground (Cost: 1.0)
        # 1: Dense Brush / Heavy Vegetation (Cost: 3.0)
        # 2: Impassable Obstacle / Rock (Cost: inf)
        # 3: Burning Fire (Impassable / Hazardous)
        # 4: Burned Out / Ash (Cost: 2.0)
        self.grid = np.zeros((height, width), dtype=int)
        
        # Track burn duration ticks for active fires
        self.fire_grid = np.zeros((height, width), dtype=int)
        
        # List of survivors to be rescued
        self.survivors = []
        
        self._initialize_terrain()
        self._initialize_survivors()

    def _initialize_terrain(self):
        """Randomly populate terrain with open ground, brush, and obstacles."""
        for y in range(self.height):
            for x in range(self.width):
                val = np.random.rand()
                if val < 0.12:
                    self.grid[y, x] = 2  # Obstacle / Rock
                elif val < 0.38:
                    self.grid[y, x] = 1  # Dense Brush (Fuel)
                else:
                    self.grid[y, x] = 0  # Open Ground

    def _initialize_survivors(self, num_survivors=6):
        """Randomly place survivors on non-obstacle tiles."""
        placed = 0
        while placed < num_survivors:
            x = np.random.randint(0, self.width)
            y = np.random.randint(0, self.height)
            if self.grid[y, x] != 2:  # Ensure not an obstacle
                if not any(s['pos'] == (x, y) for s in self.survivors):
                    self.survivors.append({
                        'id': placed + 1,
                        'pos': (x, y),
                        'injury_severity': np.random.choice(['Low', 'Moderate', 'Critical']),
                        'rescued': False,
                        'status': 'active',  # 'active', 'rescued', or 'burned'
                        'discovered_at_tick': None
                    })
                    placed += 1

    def initialize_fire(self, start_coords):
        """Set initial fire ignition points (list of (y, x) tuples)."""
        for y, x in start_coords:
            if 0 <= y < self.height and 0 <= x < self.width:
                self.grid[y, x] = 3
                self.fire_grid[y, x] = 8  # Burn duration ticks

    def update_fire(self, wind_direction="East"):
        """Cellular automaton rule for fire spread with balanced spread probabilities."""
        new_grid = self.grid.copy()
        new_fire_grid = self.fire_grid.copy()
        
        for y in range(self.height):
            for x in range(self.width):
                if self.grid[y, x] == 3:  # Currently burning
                    new_fire_grid[y, x] -= 1
                    if new_fire_grid[y, x] <= 0:
                        new_grid[y, x] = 4  # Burned out / Ash
                
                elif self.grid[y, x] in [0, 1, 4]:  # Unburned fuel, open ground, or ash
                    if self.grid[y, x] != 4 and self._has_burning_neighbor(y, x):
                        # Lowered base ignition probabilities to prevent instant grid consumption
                        ignition_prob = 0.22 if self.grid[y, x] == 1 else 0.08
                        
                        # Adjust probability based on wind direction
                        if wind_direction == "East" and x > 0 and self.grid[y, x-1] == 3:
                            ignition_prob += 0.12
                        elif wind_direction == "West" and x < self.width - 1 and self.grid[y, x+1] == 3:
                            ignition_prob += 0.12
                        elif wind_direction == "South" and y > 0 and self.grid[y-1, x] == 3:
                            ignition_prob += 0.12
                        elif wind_direction == "North" and y < self.height - 1 and self.grid[y+1, x] == 3:
                            ignition_prob += 0.12
                            
                        if np.random.rand() < ignition_prob:
                            new_grid[y, x] = 3
                            new_fire_grid[y, x] = 8  # Set burn duration ticks
                            
        self.grid = new_grid
        self.fire_grid = new_fire_grid

        # Check if fire has consumed any active survivors
        for s in self.survivors:
            if s['status'] == 'active':
                sx, sy = s['pos']
                if self.grid[sy, sx] == 3:  # Fire reached them
                    s['status'] = 'burned'
                    print(f"[FATAL] Fire reached Survivor ID {s['id']}! Could not save.")

    def suppress_fire(self, y, x):
        """Extinguishes an active fire cell, converting it to ash (4)."""
        if 0 <= y < self.height and 0 <= x < self.width:
            if self.grid[y, x] == 3:
                self.grid[y, x] = 4
                self.fire_grid[y, x] = 0
                return True
        return False

    def get_statistics(self):
        """Returns grid telemetry for live analytics HUD and reports."""
        active_fires = np.sum(self.grid == 3)
        burned_ash = np.sum(self.grid == 4)
        containment_ratio = (burned_ash / (active_fires + burned_ash + 1)) * 100
        return {
            'active_fires': active_fires,
            'burned_ash': burned_ash,
            'containment_pct': round(containment_ratio, 1)
        }

    def _has_burning_neighbor(self, y, x):
        """Checks 8-directional Moore neighborhood for active fire cells."""
        neighbors = [
            (y-1, x), (y+1, x), (y, x-1), (y, x+1),
            (y-1, x-1), (y-1, x+1), (y+1, x-1), (y+1, x+1)
        ]
        for ny, nx in neighbors:
            if 0 <= ny < self.height and 0 <= nx < self.width:
                if self.grid[ny, nx] == 3:
                    return True
        return False

    def get_terrain_cost(self, y, x):
        """Returns dynamic movement cost for A* pathfinding."""
        cell_type = self.grid[y, x]
        if cell_type == 0:
            return 1.0   # Open Ground
        elif cell_type == 1:
            return 3.0   # Dense Brush
        elif cell_type == 4:
            return 2.0   # Burned Out / Ash
        else:
            return float('inf')  # Obstacle (2) or Active Fire (3) is impassable