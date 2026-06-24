import os
import subprocess
import glob
import sys

def main():
    tests_dir = "/Users/sarthakraghubanshi/Documents/Intelligent Customer Support Assistant/tests"
    test_files = glob.glob(os.path.join(tests_dir, "verify_*.py"))
    test_files.sort()

    print(f"Found {len(test_files)} test files to execute.")
    results = []

    for test_file in test_files:
        basename = os.path.basename(test_file)
        try:
            res = subprocess.run(
                ["python3", test_file],
                cwd="/Users/sarthakraghubanshi/Documents/Intelligent Customer Support Assistant",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            exit_code = res.returncode
            status = "PASS" if exit_code == 0 else "FAIL"
            results.append((basename, status, exit_code, res.stdout, res.stderr))
        except subprocess.TimeoutExpired:
            results.append((basename, "TIMEOUT", -1, "", "Execution timed out after 30 seconds"))
        except Exception as e:
            results.append((basename, "FAIL", -99, "", str(e)))

    total = len(results)
    passed = sum(1 for r in results if r[1] == "PASS")
    failed = total - passed

    print("\n==============================================")
    print("DETAILED TEST VERIFICATION RUN SUMMARY")
    print("==============================================")
    for basename, status, code, stdout, stderr in results:
        print(f"File: {basename} | Status: {status} | Exit Code: {code}")
        if status != "PASS":
            print(f"--- Stderr for {basename} ---")
            print(stderr)
            print(f"--- Stdout for {basename} ---")
            print(stdout)
            print("-----------------------------")
    
    print("\n==============================================")
    print(f"TOTAL TESTS: {total} | PASSED: {passed} | FAILED: {failed}")
    print("==============================================")
    
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
