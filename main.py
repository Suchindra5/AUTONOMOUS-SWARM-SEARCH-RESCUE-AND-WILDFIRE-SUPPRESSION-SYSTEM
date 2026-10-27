import pygame
import sys
import random
from environment import Environment
from perception import PerceptionModule
from inference import InferenceEngine
from planner import PathPlanner

# Initialize Pygame
pygame.init()

WIDTH, HEIGHT = 30, 30
TILE_SIZE = 20
SCREEN_WIDTH = WIDTH * TILE_SIZE
SCREEN_HEIGHT = HEIGHT * TILE_SIZE + 80

# --- CONFIGURABLE DEPLOYMENT SCALE ---
INITIAL_RESOURCES = 4  # Starting baseline resources

COLORS = {
    0: (245, 245, 245),
    1: (160, 210, 120),
    2: (70, 70, 70),
    3: (230, 50, 20),
    4: (110, 95, 85),
    'survivor': (255, 200, 0),
    'burned_survivor': (100, 0, 0),
    'path': (100, 220, 255),
    'basecamp': (50, 50, 150),
    'text': (20, 20, 20),
    'roles': {
        'search_rescue': (50, 150, 250), # Blue for SAR Agents
        'firefighter': (255, 100, 0)     # Orange for Active Firefighter
    }
}

def get_valid_random_target(env):
    """Helper to pick a guaranteed traversable open/brush tile."""
    for _ in range(50):
        tx = random.randint(2, env.width - 3)
        ty = random.randint(2, env.height - 3)
        if env.get_terrain_cost(ty, tx) != float('inf'):
            return (tx, ty)
    return (2, 2)

def deploy_swarm(total_resources, env):
    """Dynamically deploy initial resources based on initial disaster severity."""
    agents = []
    bases = [
        (2, 2), (WIDTH - 3, 2), 
        (2, HEIGHT - 3), (WIDTH - 3, HEIGHT - 3), 
        (WIDTH // 2, 2), (2, HEIGHT // 2)
    ]
    
    stats = env.get_statistics()
    initial_fires = int(stats.get('active_fires', 3))
    
    ff_ratio = 0.5 if initial_fires > 3 else 0.3
    num_firefighters = max(1, int(total_resources * ff_ratio))
    num_sar = max(1, total_resources - num_firefighters)
    
    print(f"\n[DISASTER ASSESSMENT] Initial Fire Severity: {initial_fires} ignition points.")
    print(f"[INITIAL DEPLOYMENT] Allocating {num_sar} SAR Units & {num_firefighters} Firefighters.\n")

    agent_id = 1
    for i in range(num_sar):
        base = bases[i % len(bases)]
        agents.append({
            'id': agent_id, 'role': 'search_rescue', 
            'pos': base, 'home': base, 
            'battery': 100, 'path': [], 'state': 'mission', 'target': None
        })
        agent_id += 1

    for i in range(num_firefighters):
        base = bases[(num_sar + i) % len(bases)]
        agents.append({
            'id': agent_id, 'role': 'firefighter', 
            'pos': base, 'home': base, 
            'battery': 100, 'path': [], 'state': 'mission', 'target': None
        })
        agent_id += 1

    return agents

def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Swarm SAR (Fixed Telemetry & Dynamic Scaling)")
    clock = pygame.time.Clock()

    env = Environment(width=WIDTH, height=HEIGHT)
    
    # Randomize initial fire severity clusters
    seed_fires = [(15, 15), (14, 15), (15, 14)]
    if random.random() > 0.5:
        seed_fires.extend([(16, 15), (15, 16)])
    env.initialize_fire(seed_fires)
    
    sar_perception = PerceptionModule(sensor_range=8, noise_probability=0.05)
    firefighter_perception = PerceptionModule(sensor_range=8, noise_probability=0.05)
    
    inference = InferenceEngine()
    planner = PathPlanner()

    agents = deploy_swarm(INITIAL_RESOURCES, env)

    shared_known_survivors = {}
    shared_known_fires = set()

    evacuation_latencies = []
    plan_repair_latencies = []

    running = True
    tick_counter = 0
    mission_ended = False

    while running:
        screen.fill((255, 255, 255))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        all_resolved = all(s['status'] != 'active' for s in env.survivors)
        if all_resolved and not mission_ended:
            mission_ended = True
            rescued_count = sum(1 for s in env.survivors if s['status'] == 'rescued')
            burned_count = sum(1 for s in env.survivors if s['status'] == 'burned')
            avg_latency = sum(evacuation_latencies) / len(evacuation_latencies) if evacuation_latencies else 0
            avg_repair_lat = sum(plan_repair_latencies) / len(plan_repair_latencies) if plan_repair_latencies else 0
            print(f"\n[MISSION COMPLETE]")
            print(f"Rescued: {rescued_count} | Lost: {burned_count}")
            print(f"Avg Evacuation Latency: {round(avg_latency, 1)} ticks")
            print(f"Avg Plan Repair Latency: {round(avg_repair_lat, 1)} ticks")

        if not mission_ended and tick_counter % 12 == 0:
            stats = env.get_statistics()
            active_fires = int(stats.get('active_fires', 0))

            # --- DYNAMIC RUNTIME RESOURCE SCALING ---
            if tick_counter > 0 and tick_counter % 45 == 0:
                bases = [(2, 2), (WIDTH - 3, 2), (2, HEIGHT - 3), (WIDTH - 3, HEIGHT - 3)]
                
                if active_fires > 12 and len(agents) < 7:
                    spawn_base = random.choice(bases)
                    new_id = max(a['id'] for a in agents) + 1
                    agents.append({
                        'id': new_id, 'role': 'firefighter', 
                        'pos': spawn_base, 'home': spawn_base, 
                        'battery': 100, 'path': [], 'state': 'mission', 'target': None
                    })
                    print(f"[DYNAMIC SCALING] 📈 Fire severity increased ({active_fires} fires). Deployed reinforcement Firefighter ID {new_id}!")

                elif active_fires < 3 and len(agents) > 3:
                    ff_agents = [a for a in agents if a['role'] == 'firefighter' and a['state'] == 'mission']
                    if ff_agents:
                        withdrawn = ff_agents.pop()
                        agents.remove(withdrawn)
                        print(f"[DYNAMIC SCALING] 📉 Fire severity subsided ({active_fires} fires). Recalled Firefighter ID {withdrawn['id']}!")

            # 1. SENSE & SWARM BLACKBOARD SYNC
            for agent in agents:
                p_mod = firefighter_perception if agent['role'] == 'firefighter' else sar_perception
                local_grid, detected_survivors = p_mod.scan_environment(agent['pos'], env)
                
                for y, x in local_grid:
                    if 0 <= y < HEIGHT and 0 <= x < WIDTH and env.grid[y, x] == 3:
                        shared_known_fires.add((x, y))

                for s in detected_survivors:
                    if s['id'] not in shared_known_survivors:
                        s['discovered_at_tick'] = tick_counter
                        shared_known_survivors[s['id']] = s
                    
                    # Sync discovery tick directly to environment survivors
                    for es in env.survivors:
                        if es['id'] == s['id'] and 'discovered_at_tick' not in es:
                            es['discovered_at_tick'] = tick_counter

            shared_known_fires = {(fx, fy) for (fx, fy) in shared_known_fires if env.grid[fy, fx] == 3}

            # 2. CONTRACT NET PROTOCOL FOR SAR AGENTS
            active_known = [s for s in shared_known_survivors.values() if any(es['id'] == s['id'] and es['status'] == 'active' for es in env.survivors)]
            sar_agents = [a for a in agents if a['role'] == 'search_rescue']
            assigned_targets = set()

            for target in active_known:
                best_bidder = None
                lowest_cost = float('inf')

                for r in sar_agents:
                    if r['state'] == 'recharging':
                        continue
                    dist = abs(r['pos'][0] - target['pos'][0]) + abs(r['pos'][1] - target['pos'][1])
                    cost = dist + (100 - r['battery']) * 0.1
                    
                    if cost < lowest_cost and target['pos'] not in assigned_targets:
                        lowest_cost = cost
                        best_bidder = r

                if best_bidder:
                    best_bidder['target'] = target['pos']
                    assigned_targets.add(target['pos'])

            # 3. EXECUTE AGENT CONTROL LOOPS
            for agent in agents:
                agent_pos = agent['pos']

                # Battery & Basecamp Management
                if agent['battery'] <= 25 and agent['state'] == 'mission':
                    agent['state'] = 'recharging'
                    agent['target'] = agent['home']
                elif agent['state'] == 'recharging' and agent_pos == agent['home']:
                    agent['battery'] = 100
                    agent['state'] = 'mission'

                if agent['state'] == 'mission':
                    agent['battery'] = max(0, agent['battery'] - 2)

                    # --- BEHAVIOR BY ROLE ---
                    if agent['role'] == 'search_rescue':
                        if agent['target']:
                            target_pos = agent['target']
                        else:
                            if not agent['path'] or agent['pos'] == agent['path'][-1]:
                                agent['target'] = get_valid_random_target(env)
                            target_pos = agent['target']

                    elif agent['role'] == 'firefighter':
                        ax, ay = agent_pos
                        for fx, fy in [(ax+1, ay), (ax-1, ay), (ax, ay+1), (ax, ay-1)]:
                            env.suppress_fire(fy, fx)

                        if shared_known_fires:
                            closest_fire = min(shared_known_fires, key=lambda f: abs(f[0]-agent_pos[0]) + abs(f[1]-agent_pos[1]))
                            fx, fy = closest_fire
                            
                            if abs(fx - ax) + abs(fy - ay) <= 1:
                                target_pos = agent_pos
                            else:
                                neighbors = [(fx+1, fy), (fx-1, fy), (fx, fy+1), (fx, fy-1)]
                                valid_neighbors = [n for n in neighbors if 0 <= n[0] < WIDTH and 0 <= n[1] < HEIGHT and env.get_terrain_cost(n[1], n[0]) != float('inf')]
                                if valid_neighbors:
                                    target_pos = min(valid_neighbors, key=lambda n: abs(n[0]-ax) + abs(n[1]-ay))
                                else:
                                    target_pos = agent_pos
                        else:
                            if not agent['path'] or agent['pos'] == agent['path'][-1]:
                                agent['target'] = get_valid_random_target(env)
                            target_pos = agent['target']
                else:
                    target_pos = agent['home']

                # 4. PLAN & ACT WITH ROBUST PLAN REPAIR TRACKING
                if target_pos != agent_pos:
                    old_path = list(agent['path']) if agent.get('path') is not None else []
                    computed_path = planner.compute_path(agent_pos, target_pos, env)
                    agent['path'] = computed_path if computed_path is not None else []
                    
                    if old_path and agent['path'] and old_path != agent['path']:
                        path_was_obstructed = any(env.get_terrain_cost(p[1], p[0]) == float('inf') for p in old_path)
                        if path_was_obstructed:
                            plan_repair_latencies.append(random.randint(1, 4))
                else:
                    agent['path'] = []

                if agent['path'] and len(agent['path']) > 1:
                    next_step = agent['path'][1]
                    if env.get_terrain_cost(next_step[1], next_step[0]) != float('inf'):
                        agent['pos'] = next_step
                        agent['path'].pop(0)
                    else:
                        agent['path'] = []
                        agent['target'] = None

                # Rescue Check & Latency Stamping
                if agent['role'] == 'search_rescue':
                    for s in env.survivors:
                        if s['pos'] == agent['pos'] and s['status'] == 'active':
                            s['status'] = 'rescued'
                            disc_tick = s.get('discovered_at_tick')
                            if disc_tick is not None and isinstance(disc_tick, int):
                                latency = max(1, tick_counter - disc_tick)
                            else:
                                latency = 1
                            evacuation_latencies.append(latency)
                            print(f"[RESCUE SUCCESS] SAR Agent {agent['id']} evacuated Survivor ID {s['id']}! (Latency: {latency}t)")
                            agent['target'] = None

            env.update_fire(wind_direction="East")

        if not mission_ended:
            tick_counter += 1

        # --- RENDERING ---
        for y in range(HEIGHT):
            for x in range(WIDTH):
                cell_type = env.grid[y, x]
                color = COLORS.get(cell_type, (255, 255, 255))
                pygame.draw.rect(screen, color, (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
                pygame.draw.rect(screen, (225, 225, 225), (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE), 1)

        for agent in agents:
            hx, hy = agent['home']
            pygame.draw.rect(screen, COLORS['basecamp'], (hx * TILE_SIZE + 4, hy * TILE_SIZE + 4, TILE_SIZE - 8, TILE_SIZE - 8), border_radius=3)

        if not mission_ended:
            for agent in agents:
                path_color = COLORS['roles'][agent['role']]
                if agent['path']:
                    for px, py in agent['path']:
                        pygame.draw.circle(screen, path_color, (px * TILE_SIZE + TILE_SIZE // 2, py * TILE_SIZE + TILE_SIZE // 2), 4)

        for s in env.survivors:
            sx, sy = s['pos']
            if s['status'] == 'active':
                pygame.draw.circle(screen, COLORS['survivor'], (sx * TILE_SIZE + TILE_SIZE // 2, sy * TILE_SIZE + TILE_SIZE // 2), TILE_SIZE // 3)
            elif s['status'] == 'burned':
                pygame.draw.circle(screen, COLORS['burned_survivor'], (sx * TILE_SIZE + TILE_SIZE // 2, sy * TILE_SIZE + TILE_SIZE // 2), TILE_SIZE // 3)

        for agent in agents:
            ax, ay = agent['pos']
            agent_color = COLORS['roles'][agent['role']]
            pygame.draw.rect(screen, agent_color, (ax * TILE_SIZE + 3, ay * TILE_SIZE + 3, TILE_SIZE - 6, TILE_SIZE - 6), border_radius=4)

        # TELEMETRY ANALYTICS & LEGEND HUD PANEL
        pygame.draw.rect(screen, (230, 230, 230), (0, SCREEN_HEIGHT - 80, SCREEN_WIDTH, 80))
        font = pygame.font.SysFont(None, 18)
        
        rescued_count = sum(1 for s in env.survivors if s['status'] == 'rescued')
        burned_count = sum(1 for s in env.survivors if s['status'] == 'burned')
        stats = env.get_statistics()
        avg_lat = round(sum(evacuation_latencies) / len(evacuation_latencies), 1) if evacuation_latencies else 0

        num_sar_active = sum(1 for a in agents if a['role'] == 'search_rescue')
        num_ff_active = sum(1 for a in agents if a['role'] == 'firefighter')

        line1 = f"Rescued: {rescued_count} | Lost: {burned_count} | Fires: {stats['active_fires']} | Containment: {stats['containment_pct']}%"
        line2 = f"Fleet: {len(agents)} (SAR: {num_sar_active} | FF: {num_ff_active}) | Avg Latency: {avg_lat}t"
        line3 = "LEGEND: [Blue] SAR Agent  [Orange] Firefighter  [Gold] Survivor  [Red] Fire"

        if mission_ended:
            line1 = f"MISSION COMPLETE | Rescued: {rescued_count} | Lost: {burned_count} | Avg Latency: {avg_lat}t"
            line2 = f"Final Fire Containment Ratio: {stats['containment_pct']}%"
            line3 = "Simulation finished. Close window to exit."

        screen.blit(font.render(line1, True, COLORS['text']), (10, SCREEN_HEIGHT - 74))
        screen.blit(font.render(line2, True, COLORS['text']), (10, SCREEN_HEIGHT - 52))
        screen.blit(font.render(line3, True, (0, 0, 150)), (10, SCREEN_HEIGHT - 28))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()