import datetime
import logging
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional, Tuple

import gymnasium as gym
import matplotlib.pyplot as plt
import numpy as np
import zmq
from .utils import (
    KEY_MAP,
    pack_pb_action,
    start_minetest_client,
    start_minetest_server,
    read_config_file,
    write_config_file,
    unpack_pb_obs,
)

import pkg_resources


class Minetest(gym.Env):
    metadata = {"render_modes": ["rgb_array", "human"], "render_fps": 20}
    default_display_size = (1024, 600)

    def __init__(
        self,
        env_port: int = 5555,
        server_port: int = 30000,
        minetest_root: Optional[os.PathLike] = None,
        world_dir: Optional[os.PathLike] = None,
        config_path: Optional[os.PathLike] = None,
        display_size: Tuple[int, int] = default_display_size,
        headless: bool = False,
        fov: int = 72,
        render_mode: str = "human",
        artefact_dir: Optional[os.PathLike] = None, # ??? Path to store minetest artefacts and outputs
        start_minetest: bool = True,
        dtime: float = 0.05,
        sync_port: Optional[int] = None,
        sync_dtime: Optional[float] = None,
        client_name: str = "minetest-gymnasium",
        base_seed: int = 0,
        world_seed: Optional[int] = None,
        config_dict: Dict[str, Any] = {},
        game_id: str = "minetest",
        clientmods: List[str] = [],
        servermods: List[str] = [],
    ):
        """
        Args:
            env_port: port for communication with the minetest client
            server_port: port for the minetest server
        """

        self.unique_env_id = str(uuid.uuid4())

        # Graphics settings
        self._set_graphics(headless, display_size, fov, render_mode) 

        # Define action and observation space
        self._configure_spaces()

        # Define Minetest paths
        self._set_artefact_dirs(artefact_dir, world_dir, config_path)  # Stores minetest artefacts and outputs
        self._set_minetest_dirs(minetest_root)  # Stores actual minetest dirs and executable

        # Whether to start minetest server and client
        self.start_minetest = start_minetest

        # Used ports
        self.env_port = env_port  # MT env <-> MT client
        self.server_port = server_port  # MT client <-> MT server
        self.sync_port = sync_port  # MT client <-> MT server


        self.dtime = dtime
        self.sync_dtime = sync_dtime

        #Client Name
        self.client_name = client_name 

        # ZMQ objects
        self.socket = None
        self.context = None

        # Minetest processes
        self.server_process = None
        self.client_process = None

        # Env objects
        self.last_obs = None
        self.render_fig = None
        self.render_img = None

        # Seed the environment
        self.base_seed = base_seed
        self.world_seed = world_seed
        # If no world_seed is provided
        # seed the world with a random seed
        # generated by the RNG from base_seed
        self.reseed_on_reset = world_seed is None
        self._seed(self.base_seed)

        # Write minetest.conf
        self.config_dict = config_dict
        self._write_config()


        # Configure logging
        logging.basicConfig(
            filename=os.path.join(self.log_dir, f"env_{self.unique_env_id}.log"),
            filemode="a",
            format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
            level=logging.DEBUG,
        )

        # Configure game and mods
        self.game_id = game_id
        self.clientmods = clientmods
        self.servermods = servermods
        if self.sync_port:
            self.servermods += ["rewards"]  # require the server rewards mod
            self._enable_servermods()
        else:
            self.clientmods += ["rewards"]  # require the client rewards med
            # add client mod names in case they entail a server side component
            self.servermods += clientmods
            self._enable_clientmods()
            self._enable_servermods()


    
    def _set_graphics(self, headless: bool, display_size: Tuple[int, int], fov: int, render_mode: str):
        # gymnasium render mode
        self.render_mode = render_mode
        # minetest graphics settings
        self.headless = headless
        self.display_size = display_size
        self.fov_y = fov # vertical field of view?
        self.fov_x = self.fov_y * self.display_size[0] / self.display_size[1]

    def _configure_spaces(self):
        # Define action and observation space
        self.max_mouse_move_x = self.display_size[0]
        self.max_mouse_move_y = self.display_size[1]
        self.action_space = gym.spaces.Dict(
            {
                **{key: gym.spaces.Discrete(2) for key in KEY_MAP.keys()},
                **{
                    "MOUSE": gym.spaces.Box(
                        np.array([-1, -1]),
                        np.array([1, 1]),
                        shape=(2,),
                        dtype=float,
                    ),
                },
            },
        )
        self.observation_space = gym.spaces.Box(
            0,
            255,
            shape=(self.display_size[1], self.display_size[0], 3),
            dtype=np.uint8,
        )

    def _set_artefact_dirs(self, artefact_dir, world_dir, config_path):
        if artefact_dir is None:
            self.artefact_dir = os.path.join(os.getcwd(), "artefacts")
        else:
            self.artefact_dir = artefact_dir

        if config_path is None:
            self.clean_config = True
            self.config_path = os.path.join(self.artefact_dir, f"{self.unique_env_id}.conf")
        else:
            self.clean_config = True
            self.config_path = config_path
        
        if world_dir is None:
            self.reset_world = True 
            self.world_dir = os.path.join(self.artefact_dir, self.unique_env_id)
        else:
            self.reset_world = False
            self.world_dir = world_dir

        self.log_dir = os.path.join(self.artefact_dir, "log")
        self.media_cache_dir = os.path.join(self.artefact_dir, "media_cache")

        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.media_cache_dir, exist_ok=True)

    def _set_minetest_dirs(self, minetest_root):
        self.minetest_root = minetest_root
        if self.minetest_root is None:
            #check for local install
            candidate_minetest_root = os.path.dirname(os.path.dirname(__file__))
            candidate_minetest_executable = os.path.join(os.path.dirname(os.path.dirname(__file__)),"minetest")
            if os.path.isfile(candidate_minetest_executable):
                self.minetest_root = candidate_minetest_root

        if self.minetest_root is None: 
            #check for package install
            try:
                candidate_minetest_executable = pkg_resources.resource_filename(__name__,os.path.join("minetest","minetest"))
                if os.path.isfile(candidate_minetest_executable):
                    self.minetest_root = os.path.dirname(os.path.dirname(candidate_minetest_executable))
            except Exception as e:
                logging.warning(f"Error loading resource file 'minetest': {e}")
        # self.minetest_root = "/opt/homebrew/Cellar/minetest/5.8.0/bin/minetest"
        if self.minetest_root is None:
            raise Exception("Unable to locate minetest executable")
        
        if self.headless:
            self.minetest_executable = os.path.join(self.minetest_root,"minetest_headless")
        else:
            self.minetest_executable = os.path.join(self.minetest_root,"minetest")
        
        self.cursor_image_path = os.path.join(
            self.minetest_root,
            "cursors",
            "mouse_cursor_white_16x16.png",
        )
    
    def _seed(self, seed: Optional[int] = None):
        # for reproducibility we only reset the RNG if it was not set before
        # or if a seed is provided to avoid the use of kernel RNG/time seeding
        # Note: kernel RNG/time seeding is still used if the inital seed=None
        if self._np_random is None or (self._np_random is not None and seed is not None):
            self._np_random = np.random.default_rng(seed)
    
    def _sample_world_seed(self):
        self.world_seed = self._np_random.integers(np.iinfo(np.int64).max)

    def _write_config(self):
        config = dict(
            # Base config
            mute_sound=True,
            show_debug=False,
            enable_client_modding=True,
            csm_restriction_flags=0,
            enable_mod_channels=True,
            screen_w=self.display_size[0],
            screen_h=self.display_size[1],
            fov=self.fov_y,
            # Adapt HUD size to display size
            hud_scaling=self.display_size[0] / Minetest.default_display_size[0],
            # Experimental settings to improve performance
            server_map_save_interval=1000000,
            profiler_print_interval=0,
            active_block_range=2,
            abm_time_budget=0.01,
            abm_interval=0.1,
            active_block_mgmt_interval=4.0,
            server_unload_unused_data_timeout=1000000,
            client_unload_unused_data_timeout=1000000,
            full_block_send_enable_min_time_from_building=0.,
            max_block_send_distance=100,
            max_block_generate_distance=100,
            num_emerge_threads=0,
            emergequeue_limit_total=1000000,
            emergequeue_limit_diskonly=1000000,
            emergequeue_limit_generate=1000000,
            fps_max=1000,
            fps_max_unfocused=1000,
        )
        # Update config from existing config file
        if os.path.exists(self.config_path):
            config.update(read_config_file(self.config_path))
        # Seed the map generator if not using a custom map
        if self.world_seed:
            config.update(fixed_map_seed=self.world_seed)
        # Set from custom config dict
        config.update(self.config_dict)
        write_config_file(self.config_path, config)

    def _delete_config(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def _enable_clientmods(self):
        clientmods_folder = os.path.realpath(
            os.path.join(os.path.dirname(self.minetest_executable), "../clientmods"),
        )
        if not os.path.exists(clientmods_folder):
            # raise RuntimeError(f"Client mods must be located at {clientmods_folder}!")
            print(RuntimeWarning(f"Client mods must be located at {clientmods_folder}!"))
            return
        # Write mods.conf to enable client mods
        with open(os.path.join(clientmods_folder, "mods.conf"), "w") as mods_config:
            for clientmod in self.clientmods:
                clientmod_folder = os.path.join(clientmods_folder, clientmod)
                if not os.path.exists(clientmod_folder):
                    logging.warning(
                        f"Client mod {clientmod} was not found!"
                        " It must be located at {clientmod_folder}.",
                    )
                else:
                    mods_config.write(f"load_mod_{clientmod} = true\n")

    def _enable_servermods(self):
        # Check if there are any server mods
        servermods_folder = os.path.realpath(
            os.path.join(os.path.dirname(self.minetest_executable), "../mods"),
        )
        if not os.path.exists(servermods_folder):
            # raise RuntimeError(f"Server mods must be located at {servermods_folder}!")
            print(RuntimeWarning(f"Server mods must be located at {servermods_folder}!"))
            return
        # Create world_dir/worldmods folder
        worldmods_folder = os.path.join(self.world_dir, "worldmods")
        os.makedirs(worldmods_folder, exist_ok=True)
        # Copy server mods to world_dir/worldmods
        for mod in self.servermods:
            mod_folder = os.path.join(servermods_folder, mod)
            world_mod_folder = os.path.join(worldmods_folder, mod)
            if not os.path.exists(mod_folder):
                logging.warning(
                    f"Server mod {mod} was not found!"
                    f" It must be located at {mod_folder}.",
                )
            else:
                shutil.copytree(mod_folder, world_mod_folder, dirs_exist_ok=True)

    def _delete_world(self):
        if os.path.exists(self.world_dir):
            shutil.rmtree(self.world_dir, ignore_errors=True)

    def _reset_minetest(self):
        # Determine log paths
        reset_timestamp = datetime.datetime.now().strftime("%m-%d-%Y,%H:%M:%S")
        log_path = os.path.join(
            self.log_dir,
            f"{{}}_{reset_timestamp}_{self.unique_env_id}.log",
        )

        # Close Mintest processes
        if self.server_process:
            self.server_process.kill()
        if self.client_process:
            self.client_process.kill()

        # (Re)start Minetest server
        self.server_process = start_minetest_server(
            self.minetest_executable,
            self.config_path,
            log_path,
            self.server_port,
            self.world_dir,
            self.sync_port,
            self.sync_dtime,
            self.game_id,
        )

        # (Re)start Minetest client
        self.client_process = start_minetest_client(
            self.minetest_executable,
            self.config_path,
            log_path,
            self.env_port,
            self.server_port,
            self.cursor_image_path,
            self.client_name,
            self.media_cache_dir,
            sync_port=self.sync_port,
            dtime=self.dtime,
            headless=self.headless,
        )


    def reset(self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None):
        self._seed(seed=seed)
        if self.start_minetest:
            if self.reset_world:
                self._delete_world()
                if self.reseed_on_reset:
                    self._sample_world_seed()
                self._write_config()
            self._enable_servermods()
            self._reset_minetest()
        self._reset_zmq()

        # Receive initial observation
        logging.debug("Waiting for first obs...")
        byte_obs = self.socket.recv()
        obs, _, _, _, _ = unpack_pb_obs(byte_obs)
        self.last_obs = obs
        logging.debug("Received first obs: {}".format(obs.shape))
        return obs, {}
    
    def _reset_zmq(self):
        if self.socket:
            self.socket.close()
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{self.env_port}")


    def step(self, action: Dict[str, Any]):
        # Send action
        if isinstance(action["MOUSE"], np.ndarray):
            action["MOUSE"] = action["MOUSE"].tolist()
        # Scale mouse action according to screen ratio
        action["MOUSE"][0] = int(action["MOUSE"][0] * self.max_mouse_move_x)
        action["MOUSE"][1] = int(action["MOUSE"][1] * self.max_mouse_move_y)
        logging.debug("Sending action: {}".format(action))
        pb_action = pack_pb_action(action)
        self.socket.send(pb_action.SerializeToString())

        # TODO more robust check for whether a server/client is alive while receiving observations
        for process in [self.server_process, self.client_process]:
            if process is not None and process.poll() is not None:
                return self.last_obs, 0.0, True, False, {}

        # Receive observation
        logging.debug("Waiting for obs...")
        byte_obs = self.socket.recv()
        next_obs, rew, done, info, last_action = unpack_pb_obs(byte_obs)

        if last_action:
            if action != last_action:
                print("Action was not executed!")
                logging.error("Action was not executed!")

        self.last_obs = next_obs
        logging.debug(f"Received obs - {next_obs.shape}; reward - {rew}; info - {info}")
        return next_obs, rew, done, False, {"minetest_info": info}

    def render(self):
        if self.render_mode == "human":
            # TODO replace with pygame
            if self.render_img is None:
                # Setup figure
                plt.rcParams["toolbar"] = "None"
                plt.rcParams["figure.autolayout"] = True

                self.render_fig = plt.figure(
                    num="Minetest Env",
                    figsize=(3 * self.display_size[0] / self.display_size[1], 3),
                )
                self.render_img = self.render_fig.gca().imshow(self.last_obs)
                self.render_fig.gca().axis("off")
                self.render_fig.gca().margins(0, 0)
                self.render_fig.gca().autoscale_view()
            else:
                self.render_img.set_data(self.last_obs)
            plt.draw(), plt.pause(1 / self.metadata["render_fps"])
        elif self.render_mode == "rgb_array":
            return self.last_obs
        else:
            raise NotImplementedError(
                "You are calling 'render()' with an unsupported"
                f" render mode: '{self.render_mode}'. "
                f"Supported modes: {self.metadata['render_modes']}"
            )

    def close(self):
        if self.render_fig is not None:
            plt.close()
        if self.socket is not None:
            self.socket.close()
        # TODO improve process termination
        # i.e. don't kill, but close signal
        if self.client_process is not None:
            self.client_process.kill()
        if self.server_process is not None:
            self.server_process.kill()
        if self.reset_world:
            self._delete_world()
        if self.clean_config:
            self._delete_config()

