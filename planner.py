import heapq

class PathPlanner:
    def __init__(self):
        pass

    def compute_path(self, start, goal, environment):
        """
        Computes the optimal path from start to goal using A* search 
        with dynamic terrain and fire hazard costs.
        """
        width, height = environment.width, environment.height
        
        # Priority queue stores: (f_cost, g_cost, current_node, path_history)
        open_set = []
        heapq.heappush(open_set, (0.0, 0.0, start, [start]))
        
        g_costs = {start: 0.0}
        closed_set = set()
        
        # 8-directional movement allowed
        directions = [
            (0, 1), (1, 0), (0, -1), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ]
        
        while open_set:
            f, g, current, path = heapq.heappop(open_set)
            
            if current == goal:
                return path
                
            if current in closed_set:
                continue
            closed_set.add(current)
            
            cx, cy = current
            
            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy
                
                if 0 <= nx < width and 0 <= ny < height:
                    # Fetch dynamic cost from environment (returns inf if burning or obstacle)
                    terrain_cost = environment.get_terrain_cost(ny, nx)
                    if terrain_cost == float('inf'):
                        continue  # Blocked by fire or rock obstacle
                        
                    # Diagonal distance weight adjustment
                    move_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                    step_cost = terrain_cost * move_cost
                    
                    neighbor = (nx, ny)
                    new_g = g + step_cost
                    
                    if neighbor not in g_costs or new_g < g_costs[neighbor]:
                        g_costs[neighbor] = new_g
                        # Chebyshev distance heuristic for 8-way grid movement
                        h = max(abs(nx - goal[0]), abs(ny - goal[1]))
                        new_f = new_g + h
                        
                        heapq.heappush(open_set, (new_f, new_g, neighbor, path + [neighbor]))
                        
        return None  # Returns None if fire completely surrounds or blocks the target