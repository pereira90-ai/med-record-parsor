from datetime import datetime
import logging
import os
from argparse import ArgumentParser
from webapp import create_app, socketio

os.makedirs("logs", exist_ok=True)

log_file_name = datetime.now().strftime(
    os.path.join("logs", "llmanonymizer_%H_%M_%d_%m_%Y.log")
)
logging.basicConfig(
    level=logging.DEBUG,
    filename=log_file_name,
    filemode="w",
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logging.debug("Start LLM Anonymizer")

def create_parser():
    parser = ArgumentParser(description='Web app for llama-cpp')
    parser.add_argument("--model_path", type=str, default=os.getenv('MODEL_PATH', "models"), help="Path where the models are stored which llama cpp can load.")
    parser.add_argument("--server_path", type=str, default=os.getenv('SERVER_PATH', r""), help="Path to the llama server executable.")
    parser.add_argument("--port", type=int, default=int(os.getenv('PORT', 5000)), help="On which port the Web App should be available.")
    parser.add_argument("--host", type=str, default=os.getenv('HOST', "localhost"))
    parser.add_argument("--config_file", type=str, default=os.getenv('CONFIG_FILE', "config.yml"))
    parser.add_argument("--n_gpu_layers", type=int, default=int(os.getenv('N_GPU_LAYERS', 80)))
    parser.add_argument("--llamacpp_port", type=int, default=int(os.getenv('LLAMACPP_PORT', 2929)))
    parser.add_argument("--debug", action="store_true", default=os.getenv('DEBUG', 'false') == 'true')
    parser.add_argument("--mode", type=str, default=os.getenv('MODE', "choice"), choices=["anonymizer", "informationextraction", "choice"], help="Which mode to run")
    parser.add_argument("--enable_parallel", action="store_true", default=os.getenv('ENABLE_PARALLEL', 'false') == 'true', help="Parallel llama-cpp processing.")
    parser.add_argument("--parallel_slots", type=int, default=int(os.getenv('PARALLEL_SLOTS', 1)), help="Number of parallel slots for llama processing")
    parser.add_argument("--no_parallel_preprocessing", action="store_true", default=os.getenv('NO_PARALLEL_PREPROCESSING', 'false') == 'true', help="Disable parallel preprocessing")
    # kv cache type can be q4_0, q8_0, f16, f32, q5_0, q5_1, q4_1, iq4_nl
    parser.add_argument("--kv_cache_type", type=str, default=os.getenv('KV_CACHE_TYPE', 'q8_0'), choices=["q4_0", "q8_0", "f16", "f32", "q5_0", "q5_1", "q4_1", "iq4_nl"], help="KV cache type")
    parser.add_argument("--mlock", action="store_true", default=os.getenv('MLOCK', 'true') == 'true', help="Enable memory locking")
    parser.add_argument("--context_size", type=int, default=int(os.getenv('CONTEXT_SIZE', -1)), help="Set custom context size for llama cpp")
    parser.add_argument("--verbose_llama", action="store_true", default=os.getenv('VERBOSE_LLAMA', 'false') == 'true', help="Verbose llama cpp")
    parser.add_argument("--no_password", action="store_true", default=os.getenv('NO_PASSWORD', 'false') == 'true', help="Disable password protection")
    return parser


if __name__ == "__main__":

    parser = create_parser()
    args = parser.parse_args()


    app = create_app(auth_required=True if args.host != "localhost" and not args.no_password else False)

    app.config["MODEL_PATH"] = args.model_path
    app.config["SERVER_PATH"] = args.server_path
    app.config["SERVER_PORT"] = args.port
    app.config["CONFIG_FILE"] = args.config_file
    app.config["N_GPU_LAYERS"] = args.n_gpu_layers
    app.config["LLAMACPP_PORT"] = args.llamacpp_port
    app.config["DEBUG"] = args.debug
    app.config["NO_PARALLEL"] = not args.enable_parallel
    app.config["PARALLEL_SLOTS"] = args.parallel_slots
    app.config["CTX_SIZE"] = args.context_size
    app.config["VERBOSE_LLAMA"] = args.verbose_llama
    app.config["PARALLEL_PREPROCESSING"] = not args.no_parallel_preprocessing
    app.config["MLOCK"] = args.mlock
    app.config["KV_CACHE_TYPE"] = args.kv_cache_type

    app.config["MODE"] = args.mode


    # if model path is relative, make it absolute
    if not os.path.isabs(app.config["MODEL_PATH"]):
        app.config["MODEL_PATH"] = os.path.abspath(app.config["MODEL_PATH"])

    # if server path is relative, make it absolute
    if not os.path.isabs(app.config["SERVER_PATH"]):
        app.config["SERVER_PATH"] = os.path.abspath(app.config["SERVER_PATH"])

    print("Start Server on http://" + args.host + ":" + str(args.port))
    if args.host == "0.0.0.0":
        print("Please use http://localhost:" + str(args.port) + " to access the web app locally or the IP / hostname of your server to access the web app in your local network.")
    if args.host != "localhost":
        print("Requires authentication")

    socketio.run(app, debug=args.debug, use_reloader=args.debug, port=args.port, host=args.host, allow_unsafe_werkzeug=True)
