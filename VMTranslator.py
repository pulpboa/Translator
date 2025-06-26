import sys
import os

SEGMENT_BASE = {
    "local": "LCL",
    "argument": "ARG",
    "this": "THIS",
    "that": "THAT",
}

POINTER_BASE = {
    "0": "THIS",
    "1": "THAT",
}

def get_bootstrap_code():
    return [
        "// Bootstrap code",
        "@256",
        "D=A",
        "@SP",
        "M=D",
    ] + translate_call("Sys.init", 0, "bootstrap")

def translate_arithmetic(command, label_count):
    asm = [f"// {command}"]
    if command in ("neg", "not"):
        asm += [
            "@SP",
            "A=M-1",
            "M=" + ("-M" if command == "neg" else "!M")
        ]
    elif command in ("add", "sub", "and", "or"):
        asm += [
            "@SP",
            "AM=M-1",
            "D=M",
            "A=A-1"
        ]
        if command == "add":
            asm.append("M=M+D")
        elif command == "sub":
            asm.append("M=M-D")
        elif command == "and":
            asm.append("M=M&D")
        elif command == "or":
            asm.append("M=M|D")
    elif command in ("eq", "gt", "lt"):
        jump = {"eq": "JEQ", "gt": "JGT", "lt": "JLT"}[command]
        true_label = f"TRUE_{label_count}"
        end_label = f"END_{label_count}"
        asm += [
            "@SP",
            "AM=M-1",
            "D=M",
            "A=A-1",
            "D=M-D",
            f"@{true_label}",
            f"D;{jump}",
            "@SP",
            "A=M-1",
            "M=0",
            f"@{end_label}",
            "0;JMP",
            f"({true_label})",
            "@SP",
            "A=M-1",
            "M=-1",
            f"({end_label})"
        ]
    return asm

def translate_push(segment, index, file_name):
    asm = [f"// push {segment} {index}"]
    if segment == "constant":
        asm += [
            f"@{index}",
            "D=A"
        ]
    elif segment in SEGMENT_BASE:
        asm += [
            f"@{index}",
            "D=A",
            f"@{SEGMENT_BASE[segment]}",
            "A=M+D",
            "D=M"
        ]
    elif segment == "temp":
        asm += [
            f"@{5+int(index)}",
            "D=M"
        ]
    elif segment == "pointer":
        asm += [
            f"@{POINTER_BASE[index]}",
            "D=M"
        ]
    elif segment == "static":
        asm += [
            f"@{file_name}.{index}",
            "D=M"
        ]
    asm += [
        "@SP",
        "A=M",
        "M=D",
        "@SP",
        "M=M+1"
    ]
    return asm

def translate_pop(segment, index, file_name):
    asm = [f"// pop {segment} {index}"]
    if segment in SEGMENT_BASE:
        asm += [
            f"@{index}",
            "D=A",
            f"@{SEGMENT_BASE[segment]}",
            "D=M+D",
            "@R13",
            "M=D",
            "@SP",
            "AM=M-1",
            "D=M",
            "@R13",
            "A=M",
            "M=D"
        ]
    elif segment == "temp":
        asm += [
            "@SP",
            "AM=M-1",
            "D=M",
            f"@{5+int(index)}",
            "M=D"
        ]
    elif segment == "pointer":
        asm += [
            "@SP",
            "AM=M-1",
            "D=M",
            f"@{POINTER_BASE[index]}",
            "M=D"
        ]
    elif segment == "static":
        asm += [
            "@SP",
            "AM=M-1",
            "D=M",
            f"@{file_name}.{index}",
            "M=D"
        ]
    return asm

def translate_label(label, current_function):
    return [f"// label {label}", f"({current_function}${label})"]

def translate_goto(label, current_function):
    return [f"// goto {label}", f"@{current_function}${label}", "0;JMP"]

def translate_if(label, current_function):
    return [
        f"// if-goto {label}",
        "@SP",
        "AM=M-1",
        "D=M",
        f"@{current_function}${label}",
        "D;JNE"
    ]

def translate_function(function_name, n_vars):
    asm = [f"// function {function_name} {n_vars}", f"({function_name})"]
    for _ in range(int(n_vars)):
        asm += [
            "@SP",
            "A=M",
            "M=0",
            "@SP",
            "M=M+1"
        ]
    return asm

def translate_call(function_name, n_args, call_id):
    return [
        f"// call {function_name} {n_args}",
        f"@RET_{function_name}${call_id}",
        "D=A",
        "@SP",
        "A=M",
        "M=D",
        "@SP",
        "M=M+1",
        "@LCL",
        "D=M",
        "@SP",
        "A=M",
        "M=D",
        "@SP",
        "M=M+1",
        "@ARG",
        "D=M",
        "@SP",
        "A=M",
        "M=D",
        "@SP",
        "M=M+1",
        "@THIS",
        "D=M",
        "@SP",
        "A=M",
        "M=D",
        "@SP",
        "M=M+1",
        "@THAT",
        "D=M",
        "@SP",
        "A=M",
        "M=D",
        "@SP",
        "M=M+1",
        "@SP",
        "D=M",
        f"@{int(n_args)+5}",
        "D=D-A",
        "@ARG",
        "M=D",
        "@SP",
        "D=M",
        "@LCL",
        "M=D",
        f"@{function_name}",
        "0;JMP",
        f"(RET_{function_name}${call_id})"
    ]

def translate_return():
    return [
        "// return",
        "@LCL",
        "D=M",
        "@R13",
        "M=D",      # FRAME = LCL
        "@5",
        "A=D-A",
        "D=M",
        "@R14",
        "M=D",      # RET = *(FRAME-5)
        "@SP",
        "AM=M-1",
        "D=M",
        "@ARG",
        "A=M",
        "M=D",      # *ARG = pop()
        "@ARG",
        "D=M+1",
        "@SP",
        "M=D",      # SP = ARG+1
        "@R13",
        "AM=M-1",
        "D=M",
        "@THAT",
        "M=D",      # THAT = *(FRAME-1)
        "@R13",
        "AM=M-1",
        "D=M",
        "@THIS",
        "M=D",      # THIS = *(FRAME-2)
        "@R13",
        "AM=M-1",
        "D=M",
        "@ARG",
        "M=D",      # ARG = *(FRAME-3)
        "@R13",
        "AM=M-1",
        "D=M",
        "@LCL",
        "M=D",      # LCL = *(FRAME-4)
        "@R14",
        "A=M",
        "0;JMP"     # goto RET
    ]

def translate(vm_file, file_name):
    asm = []
    label_count = 0
    call_count = 0
    current_function = "Sys.init"
    with open(vm_file) as f:
        lines = f.readlines()
    for line in lines:
        line = line.strip().split("//")[0]
        if not line:
            continue
        parts = line.split()
        cmd = parts[0]
        if cmd in ("push", "pop"):
            segment, index = parts[1], parts[2]
            if cmd == "push":
                asm += translate_push(segment, index, file_name)
            else:
                asm += translate_pop(segment, index, file_name)
        elif cmd in ("add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not"):
            asm += translate_arithmetic(cmd, label_count)
            if cmd in ("eq", "gt", "lt"):
                label_count += 1
        elif cmd == "label":
            asm += translate_label(parts[1], current_function)
        elif cmd == "goto":
            asm += translate_goto(parts[1], current_function)
        elif cmd == "if-goto":
            asm += translate_if(parts[1], current_function)
        elif cmd == "function":
            current_function = parts[1]
            asm += translate_function(parts[1], parts[2])
        elif cmd == "call":
            asm += translate_call(parts[1], parts[2], call_count)
            call_count += 1
        elif cmd == "return":
            asm += translate_return()
    return asm

def main():
    if len(sys.argv) != 2:
        print("Usage: python VMTranslator.py <inputfile.vm | inputdirectory>")
        sys.exit(1)
    input_path = sys.argv[1]
    if os.path.isdir(input_path):
        vm_files = [f for f in os.listdir(input_path) if f.endswith(".vm")]
        full_paths = [os.path.join(input_path, f) for f in vm_files]
        output_path = os.path.join(input_path, os.path.basename(os.path.normpath(input_path)) + ".asm")
        asm_lines = get_bootstrap_code()
        for vm_file in full_paths:
            base_name = os.path.splitext(os.path.basename(vm_file))[0]
            asm_lines += translate(vm_file, base_name)
        with open(output_path, "w") as out:
            out.write('\n'.join(asm_lines))
    else:
        if not input_path.endswith(".vm"):
            print("Input file must have a .vm extension.")
            sys.exit(1)
        output_path = input_path.replace(".vm", ".asm")
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        asm_lines = translate(input_path, base_name)
        with open(output_path, "w") as out:
            out.write('\n'.join(asm_lines))

if __name__ == "__main__":
    main()
