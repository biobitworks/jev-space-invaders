"""Standalone server entry point."""
from demo.live_demo import serve

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--telemetry-dir")
    args = parser.parse_args()
    httpd = serve(args.host, args.port, args.telemetry_dir)
    print(f"LIVE_DEMO_URL=http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.controller._close_envs()
        httpd.server_close()
