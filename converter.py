import os
import sys
import argparse
import typing
import re
import pprint
import codecs

#Common
FIELD_TYPE_POSITION = 22
FIELD_LENGTH_START_POSITION = 23
FIELD_LENGTH_END_POSITION = 27
FIELD_LEVEL_POSITION = 28
FIELD_NAME_START_POSITION = 29
FIELD_NAME_END_POSITION = 61

#Data definition specific (**DD)
DD_FIELD_MU_FLAG_POSITION = 9
COUNTER_FLAG_POSITION = 12
MU_COMMENT_START_POSITION = 61
DD_FIELD_DEFINITION_TYPE_FLAG = 27

#**DF
DF_REDEFINE_CONST_FLAG_POSITION = 8
DF_EXTENDED_LENGTH_FLAG_POSITION = 9
DF_DATA_DEFINITION_TYPE_FLAG_POSITION = 11
DF_FILLER_FLAG_POSITION = 12
DF_INIT_LINE_COUNT_START_POSITION = 18
DF_INIT_LINE_COUNT_END_POSITION = 21
DF_START_REDEFINE_CONST_FLAG_POSITION = 27

#**DE
DE_PROPERTY_START_POSITION = 29

#View specific (**DV)
VIEW_NAME_START_POSITION = 29
VIEW_NAME_END_POSITION = 61
DDM_NAME_START_POSITION = 61


def parseArgs():
    args = {"sourcePath": "", "targetPath": ""}
    parser = argparse.ArgumentParser(prog="Fuser Converter", 
                                     description="Converts an old SAG Fuser to a vbersion which can be understood from Natural One", 
                                     epilog="Author: © Tom Engemann - 12.2023")
    parser.add_argument("-s", "--source", dest="source", 
                        required=True, help="Source path of the old fuser")
    parser.add_argument("-d", "--destination", dest="destination", 
                        required=True, help="Path to were the converted project should be written to")

    args = parser.parse_args()
    return args

def getTypefromFile(filename: str) -> str:
    file_ext_mapping = {
        ".NS7": "Functions",
        ".NSA": "Parameter Data Areas",
        ".NSC": "Copycodes",
        ".NSD": "DDMs",
        ".ERR": "Error Messages",
        ".NSG": "Global Data Areas",
        ".NSH": "Helproutines",
        ".NSL": "Local Data Areas",
        ".NSM": "Maps",
        ".NSN": "Subprograms",
        ".NSP": "Programs",
        ".NSS": "Subroutines",
        ".NST": "Texts"
    }

    filename, file_ext = os.path.splitext(filename)
    if len(file_ext) == 0:
        raise Exception(f"File extenstion for file {filename} is empty")
    
    if not file_ext in file_ext_mapping.keys():
        raise Exception(f"File extention {file_ext} not known")
    
    return file_ext_mapping[file_ext]

def extendByteArray(array: bytearray, *argv):
    target_array = array if array else bytearray()
    for v in argv:
        target_array.extend(v)
    
    return target_array

def parseCommentLine(line: bytearray, dummy=None) -> bytearray:
    length = len(line)
    if len(line) <= 23:
        return bytearray(b" ")
    if chr(line[22]) == "*" and chr(line[23]) != " ":
        return bytearray(b"* " + line[23:])
    return bytearray(line[22:])

def parseExtendedAttributes(attributes: bytearray) -> dict:
    extendedAttr = {
        "peInfo": None,
        "comment": None
    }

    if len(attributes) == 0: return extendedAttr

    for i in range(0, len(attributes)):
        if chr(attributes[i]) == "/" and chr(attributes[i+1]) == "*":
            extendedAttr["peInfo"] = bytearray(attributes[:i])
            extendedAttr["comment"] = bytearray(attributes[i:]) if len(attributes[i:]) != 0 else None
            break

    if not extendedAttr["comment"] and not extendedAttr["peInfo"]:
        extendedAttr["peInfo"] = attributes

    return extendedAttr

def parseDDLine(line: bytearray, inputfile: typing.BinaryIO) -> bytearray:
    humanReadableLine = bytearray()

    fieldLevel = int(chr(line[FIELD_LEVEL_POSITION]))
    for i in range(0, fieldLevel-1): humanReadableLine.extend(b"\t")
    humanReadableLine.extend(str(fieldLevel).encode("ascii"))
    humanReadableLine.extend(b" ")

    extendetAttr = parseExtendedAttributes(line[MU_COMMENT_START_POSITION:])
    
    counterFlag = chr(line[COUNTER_FLAG_POSITION])
    fieldName = line[FIELD_NAME_START_POSITION:FIELD_NAME_END_POSITION].strip()
    if counterFlag == "*":
        fieldName = fieldName if fieldName.startswith(b"C*") else b"C*" + fieldName
    
    humanReadableLine.extend(fieldName)
    if counterFlag == "*":
        if extendetAttr["peInfo"]:
            humanReadableLine.extend(b" ")
            humanReadableLine.extend(extendetAttr["peInfo"])
        return humanReadableLine
    
    muFlag = chr(line[DD_FIELD_MU_FLAG_POSITION])
    if muFlag == "B":
        extendedLengthLine = inputfile.readline()
        fieldLength = parseDELine(extendedLengthLine, None)
    else:
        fieldLength = line[FIELD_LENGTH_START_POSITION:FIELD_LENGTH_END_POSITION].strip()    

    
    
    fieldDefinitionType = chr(line[DD_FIELD_DEFINITION_TYPE_FLAG])
    if fieldDefinitionType == "P":
        if extendetAttr["peInfo"]:
            humanReadableLine.extend(b"(")
            humanReadableLine.extend(extendetAttr["peInfo"].replace(b"(", b"").replace(b")", b""))
            humanReadableLine.extend(b")")
        if extendetAttr["comment"]:
            humanReadableLine.extend(b" ")
            humanReadableLine.extend(extendetAttr["comment"])
        return humanReadableLine
    elif fieldDefinitionType == "G":
        if extendetAttr["comment"]:
            humanReadableLine.extend(b" ")
            humanReadableLine.extend(extendetAttr["comment"])
        return humanReadableLine

    fieldType = chr(line[FIELD_TYPE_POSITION])
    # fieldLength = line[FIELD_LENGTH_START_POSITION:FIELD_LENGTH_END_POSITION].strip()
    humanReadableLine.extend(b" (")

    if fieldDefinitionType != "P":
        humanReadableLine.extend(fieldType.encode("ascii"))
        humanReadableLine.extend(fieldLength)

    if muFlag == "I":
        if fieldDefinitionType != "P": humanReadableLine.extend(b"/")
        humanReadableLine.extend(extendetAttr["peInfo"].replace(b"(", b"").replace(b")", b""))
    humanReadableLine.extend(b")")

    if extendetAttr["comment"]:
        humanReadableLine.extend(b" ")
        humanReadableLine.extend(extendetAttr["comment"])

    return humanReadableLine

#Returns a bytearray with the length or "DYNAMIC"
def parseDELine(line: bytearray, inputfile: typing.BinaryIO) -> bytearray:
    property = line[DE_PROPERTY_START_POSITION:].strip()
    if property == b"DY":
        return b"DYNAMIC"
    equalsI = property.index(b"=")
    return property[equalsI+1:]


def parseDFLine(line: bytearray, inputfile: typing.BinaryIO) -> bytearray:
    humanReadableLine = bytearray()

    fieldLevel = int(chr(line[FIELD_LEVEL_POSITION]))
    for i in range(0, fieldLevel-1): humanReadableLine.extend(b"\t")
    humanReadableLine.extend(str(fieldLevel).encode("ascii"))
    humanReadableLine.extend(b" ")

    constRedefineFlag = chr(line[DF_START_REDEFINE_CONST_FLAG_POSITION])
    extendedLengthMUFlag = chr(line[DF_EXTENDED_LENGTH_FLAG_POSITION])
    if extendedLengthMUFlag == "B":
        extendedLengthLine = inputfile.readline()
        fieldLength = parseDELine(extendedLengthLine, None)
    else:
        fieldLength = line[FIELD_LENGTH_START_POSITION:FIELD_LENGTH_END_POSITION].strip()    
    
    dataInitTypeFlag = chr(line[DF_DATA_DEFINITION_TYPE_FLAG_POSITION])
    initLineCount = int(str(line[DF_INIT_LINE_COUNT_START_POSITION:DF_INIT_LINE_COUNT_END_POSITION].strip(), "utf-8"))
    fillerFlag = chr(line[DF_FILLER_FLAG_POSITION])

    fieldName = line[FIELD_NAME_START_POSITION:FIELD_NAME_END_POSITION].strip()
    extendetAttr = parseExtendedAttributes(line[MU_COMMENT_START_POSITION:])
    
    if constRedefineFlag == "R":
        humanReadableLine.extend(b"REDEFINE ")
    
    if fillerFlag == "F":
        humanReadableLine.extend(b"FILLER ")
    humanReadableLine.extend(fieldName)

    if constRedefineFlag == "R":
        if extendetAttr["comment"]: 
            humanReadableLine.extend(b" ")
            humanReadableLine.extend(extendetAttr["comment"])
        return humanReadableLine
    
    fieldDefinitionType = chr(line[DD_FIELD_DEFINITION_TYPE_FLAG])
    fieldType = chr(line[FIELD_TYPE_POSITION])

    if fieldType == " " and len(fieldLength) == 0:
        if extendedLengthMUFlag == "I": 
            humanReadableLine.extend(b" ")
            humanReadableLine.extend(extendetAttr["peInfo"])
        if extendetAttr["comment"]: 
            humanReadableLine.extend(b" ")
            humanReadableLine.extend(extendetAttr["comment"])
        return humanReadableLine
    
    humanReadableLine.extend(b" (")

    if fieldDefinitionType != "P":
        humanReadableLine.extend(fieldType.encode("ascii"))
        if fieldLength != b"DYNAMIC": humanReadableLine.extend(fieldLength)

    if extendedLengthMUFlag == "I":
        if fieldDefinitionType != "P": humanReadableLine.extend(b"/")
        humanReadableLine.extend(extendetAttr["peInfo"].replace(b"(", b"").replace(b")", b""))
    humanReadableLine.extend(b")")

    if fieldLength == b"DYNAMIC":
        humanReadableLine.extend(b" ")
        humanReadableLine.extend(fieldLength)

    if dataInitTypeFlag in ["S", "F"]:
        if dataInitTypeFlag == "S": 
            if constRedefineFlag == "C":
                humanReadableLine.extend(b" CONST")
            else:
                humanReadableLine.extend(b" INIT")
        initLineCount-=1
        inputfile.readline()
        if initLineCount > 1: humanReadableLine.extend(b"\n")
        for i in range(0, initLineCount):
            for i in range(0, fieldLevel): humanReadableLine.extend(b"\t")
            initLine = inputfile.readline()
            initValue = initLine[29:].strip()
            if dataInitTypeFlag == "F":
                humanReadableLine.extend(initValue)
                continue
            
            index = initLine[7:29].strip()
            humanReadableLine.extend(index)
            humanReadableLine.extend(b" <")
            if fieldType == "A": humanReadableLine.extend(b"'")
            humanReadableLine.extend(initValue)
            if fieldType == "A": humanReadableLine.extend(b"'")
            humanReadableLine.extend(b">\n")




    if extendetAttr["comment"]:
        humanReadableLine.extend(b" ")
        humanReadableLine.extend(extendetAttr["comment"])

    return humanReadableLine

def parseDKLine(line: bytearray, inputfile: typing.BinaryIO) -> bytearray:
    return parseDFLine(line, inputfile)

def parseDRLine(line: bytearray, inputfile: typing.BinaryIO) -> bytearray:
    return parseDFLine(line, inputfile)

def parseDSLine(line: bytearray, inputfile: typing.BinaryIO) -> bytearray:
    return parseDFLine(line, inputfile)

def parseDVLine(line: bytearray, inputfile: typing.BinaryIO) -> bytearray:
    humanReadableLine = bytearray()

    fieldLevel = int(chr(line[FIELD_LEVEL_POSITION]))
    for i in range(0, fieldLevel-1): humanReadableLine.extend(b"\n")
    humanReadableLine.extend(str(fieldLevel).encode("ascii"))
    humanReadableLine.extend(b" ")

    humanReadableLine.extend(line[FIELD_NAME_START_POSITION:FIELD_NAME_END_POSITION].strip())
    humanReadableLine.extend(b" VIEW OF ")
    humanReadableLine.extend(line[DDM_NAME_START_POSITION:].strip())

    return humanReadableLine

def parseDataDefinition(line: bytearray, inputfile: typing.BinaryIO) -> bytearray:
    line = line.strip()
    subType = chr(line[7])
    if subType == "D":
        return parseDDLine(line, inputfile)
    elif subType == "E":
        return parseDELine(line, inputfile)
    elif subType == "F":
        return parseDFLine(line, inputfile)
    elif subType == "K":
        return parseDKLine(line, inputfile)
    elif subType == "R":
        return parseDRLine(line, inputfile)
    elif subType == "S":
        return parseDSLine(line, inputfile)
    elif subType == "V":
        return parseDVLine(line, inputfile)

    return None

def parseInit(line: bytearray, summy=None):
    return None
    initValue = bytearray(line[29:61]).strip()
    if [ele for ele in [b"const", b"init"] if (ele in initValue.lower())]:
        return initValue
    initValueStr = initValue.decode("ascii")
    if re.match("[A-Za-z]", initValueStr):
        return bytearray(b"init <'" + initValue + b"'>")

    return bytearray(b"init <" + initValue + b">")

def transformLine(line: bytearray, member_type: str, inputfile) -> bytearray:
    line = line.strip()
    if member_type == "DDMs":
        return line
    if not  member_type in ["Global Data Areas", "Local Data Areas", "Parameter Data Areas"]:
        return line[4:].strip()
    
    try:
        line.index(b"**")
    except ValueError:
        return None

    lineHandlers = {
        "C": parseCommentLine,
        "D": parseDataDefinition,
        "H": None,
        "I": parseInit
    }

    lineType = chr(line[6])
    if not lineType in lineHandlers.keys():
            # Ignore for now to test the different handlers
            # return None
            raise Exception(f"Don't know how to parse {lineType}!")
    if not lineHandlers[lineType]: return None
    return lineHandlers[lineType](line, inputfile)

def copyMember(source_path: str, nat_type: str, target_path: str):
    with open(target_path, "wb") as new_member:
        if nat_type == "Parameter Data Areas":
            new_member.write(b"DEFINE DATA PARAMETER\n")
        elif nat_type == "Global Data Areas":
            new_member.write(b"DEFINE DATA GLOBAL\n")
        elif nat_type == "Local Data Areas":
            new_member.write(b"DEFINE DATA LOCAL\n")
            
        with open(source_path, "rb") as old_member:
                for line in old_member:
                    line = transformLine(line, nat_type, old_member)
                    if not line: continue
                    new_member.write(line.decode("iso-8859-1").encode("utf-8"))
                    # new_member.write(str(line, "utf-8"))
                    new_member.write(b"\n")
        
        if nat_type in ["Parameter Data Areas", "Global Data Areas", "Local Data Areas"]:
            new_member.write(b"END-DEFINE")
        

def handle_lib(path: str, target_dir: str, lib_name: str):
    for member in os.listdir(path):
        if member != "XXGLOB1G.NSG": continue
        source_member = os.path.join(path, member)
        try:
            nat_type = getTypefromFile(source_member)
        except Exception as e:
                print(e)
                continue
        # print(f"Found filetype {nat_type}")

        target_path = os.path.join(target_dir, lib_name, nat_type)
        os.makedirs(target_path, exist_ok=True)

        target_path = os.path.join(target_path, member)

        copyMember(source_member, nat_type, target_path)


def main():
    args = parseArgs()
    if not os.path.isdir(args.source):
        sys.stderr.write(f"{args.source} is not a directory or not found\n")
        sys.exit(1)
    
    print(f"Using root fuser {args.source}")
    for lib in os.listdir(args.source):
        lib_path = "/".join([args.source, lib])
        if not os.path.isdir(lib_path):
            continue

        lib_path = "/".join([lib_path, "SRC"])
        if not os.path.isdir(lib_path):
            print(f"No source folder found in {lib}")
            continue

        print(f"Handling lib {lib} in path {lib_path}")
        handle_lib(lib_path, args.destination, lib)

    return


if __name__ == "__main__":
    main()