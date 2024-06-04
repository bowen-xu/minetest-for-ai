#!/usr/bin/env python3
from gymnasium.wrappers import TimeLimit
from agent.env import Minetest


render = True
max_steps = 100

env = Minetest(
    base_seed=42,
    start_minetest=True,
    headless=False,
    minetest_root= "/Users/bowenxu/Codes/minetest-for-ai/build/macos/minetest.app/Contents/MacOS", #"/Users/bowenxu/Codes/minetest-for-ai/b\in/", # /Users/bowenxu/Codes/minetest-for-ai/build/macos/minetest.app/Contents/MacOS
    world_dir="/Users/bowenxu/Library/Application Support/minetest/worlds/test1"
)
env: Minetest = TimeLimit(env, max_episode_steps=max_steps)

env.reset()
done = False
step = 0
while True:
    try:
        action = env.action_space.sample()
        _, rew, done, truncated, info = env.step(action)
        print(step, rew, done or truncated, info)
        if render:
            env.render()
        if done or truncated:
            env.reset()
        step += 1
    except KeyboardInterrupt:
        break
env.close()
