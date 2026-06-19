import re
import pandas as pd

# Global Name Mapping Cache for reference lookup
COMMON_NAMES = {
    "andy": "andrew", "drew": "andrew",
    "bill": "william", "billy": "william", "will": "william",
    "bob": "robert", "rob": "robert", "bobby": "robert",
    "chris": "christopher", "chris": "christian",
    "dan": "daniel",
    "dave": "david",
    "dick": "richard", "rick": "richard",
    "greg": "gregory",
    "jeff": "jeffrey", "jeff": "jeffery", "jeff": "jefferson",
    "jim": "james", "jimmy": "james",
    "joe": "joseph",
    "john": "jonathan", "jon": "jonathan",
    "matt": "matthew",
    "mike": "michael", "mick": "michael",
    "steve": "stephen", "steve": "steven",
    "tim": "timothy",
    "tom": "thomas", "tommy": "thomas",
    
}

ALLOWED_ACRONYMS = ["LLC", "QA", "QC", "CEO", "CFO", "AISC", "QMS", "VP", "HR", "A&E", "NY", "NYC", "US", "USA", "DBA", "AP",
                    "ADF", "AF", "AFC", "AFCO", "AIC", "AIW", "AL", "ALNC", "ALW", "AM", "AMECC", "ANJ", "AOP", "ASP", "ARP", "ASE", "ATAD", "ATB", "ATS", "AXE", "AXIS", "AZCO", 
                    "BA", "BBM", "BAPKO", "BAS", "BASW", "BCS", "BES", "BMWC", "BOSS", "BR", "BSI", "BZI", 
                    "CAS", "CCP", "CCS", "CDL", "CHG", "CK", "CHM", "CMC", "CNBM", "CNC", "COI", "COOEC", "COSCO", "CPG", "CODEME", "CSCEC", "CSE", "CTI", "CW", 
                    "DAKA", "DEM", "DSE",
                    "EBC", "EDCO", "EDM", "EEI", "EMCO", "EMP", "ENDECO", "EPIC", "ESA", "ESI", "ESJ", "EZ", "FCC", "FEI", "FGA", "FL", "FM", 
                    "GDL", "GMF", "GN", "GOP", "GP", "GS", "GSI", "GSM", "GST", "GT", "HHI", "HME", "HTX", 
                    "ICM", "IG", "IHI", "II", "III", "IPC", "ISC", "IWS", "JBH", "JCB", "JGM", "JC", "JE", "JHDS", "JPW", "JSW", "JT", 
                    "KCB", "KDM", "KMH", "KK", "KW", "KWH", 
                    "LB", "LBR", "LENEX", "LJR", "LLS", "LLP", "LMC", "LNI", "LWI", 
                    "MAK", "MATHFAB", "MBI", "MCC", "MECO", "MIA", "MICA", "MMI", "MQM", "MS", "MSC", "MSD", "MSI", "MSSM", "MTH", "MX", "MYER", 
                    "NEFCO", "NIX", "NJ", "NMI", "NCC", "NTS", "NWA", "NYSFAB", "OGI", "OH", "OHC", "ORL", "OS", "OWS", 
                    "PAX", "PC", "PCL", "PDM", "PKM", "PJF", "PJR", "PMR", "POSCO", "PROMETAL", "PSP", "PT", "PTMW", "PVB", "QMF", "QSR", 
                    "RAD", "RAM", "RBC", "RBD", "RC", "REFA", "RK", "RND", "RNGD", "RNR", "ROC", "ROTHA", "RPS", "RSL", "RW", 
                    "SA", "SAC", "SAE", "SAS", "SC", "SD", "SEMMR", "SEYCO", "SIN", "SNG", "SL", "SME", "SMI", "SNS", "SOFCO", "SOS", "SPE", "SPR", "SSW", "ST", "SW", "SWF", 
                    "TAS", "TC", "TDH", "TEC", "TGOOD", "TGR", "TN", "TRC", "TZME", "UAE", "UDC", "UK", "USAS", "VAST", "VM", "WA", "WASCO", "WMK", "XKT", "XL", "ZPMC", ]
LOWERCASE_WORDS = ["de", "of", "and", "ve", "a", "an", "y"]

# The International Sub-String Override Map
# Left side = lowercase search token | Right side = Perfect target casing
INTERNATIONAL_SUFFIX_MAP = {
    "s.a.": "S.A.",
    "s.a. de c.v.": "S.A. de C.V.",
    "sa de cv": "SA de CV",
    "s. de r.l. de c.v.": "S. de R.L. de C.V.",
    "s de r.l. de c.v.": "S. de R.L. de C.V.",
    "de c.v.": "de C.V.",
    "gmbh": "GmbH",
    "s.r.l.": "S.R.L.",
    "b.v.": "B.V.",
    "n.v.": "N.V.",
    "p.c.": "P.C.",
    "s.p.a.": "S.p.A.",
    "fze": "FZE",
    "fz-llc": "FZ-LLC",
    "a.s.": "A.S.",
    "a.ş.": "A.Ş.",
    "s.a.c.": "S.A.C.",
    "l.p.": "L.P.",
    "lp": "LP",
    "co.,ltd.": "Co., Ltd.",
    "co., ltd.": "Co., Ltd.",
    "sl": "SL",
    "s.r.o.": "S.R.O.",
}

# The Master Exception Override Map (Whole Company Match)
# Left side = lowercase version of what the script would accidentally generate
# Right side = Explicit, human-verified correct casing
EXACT_COMPANY_OVERRIDES = {
    "3up metal works" : "3Up Metal Works",
    "4g steel fabrication llc" : "4G Steel Fabrication LLC",
    "a-lert construction services" : "A-Lert Construction Services",
    "a.i. industries" : "A.I. Industries",
    "all-steel fabricating, inc." : "All-Steel Fabricating, Inc.",
    "all-trade construction company inc." : "All-Trade Construction Company Inc.",
    "allmetal building systems" : "AllMetal Building Systems",
    "arcalloy custom metal fabricating & welding, llc" : "ArcAlloy Custom Metal Fabricating & Welding, LLC",
    "aspesouth" : "ASPESouth",
    "aspiredx" : "AspiredX",
    "axe build llc" : "Axe Build LLC",
    "b.g. crane services, inc." : "B.G. Crane Services, Inc.",
    "baltimore fabrication, an affiliate of steelfab - church rd" : "Baltimore Fabrication, an Affiliate of SteelFab - Church Rd",
    "baltimore fabrication, an affiliate of steelfab - mundis rd" : "Baltimore Fabrication, An Affiliate of SteelFab - Mundis Rd",
    "bbm-cpg mexicana s.a. de c.v." : "BBM-CPG Mexicana S.A. de C.V.",
    "bendtec, llc" : "BendTec, LLC",
    "c.a. hull" : "C.A. Hull",
    "c.d. smith construction, inc." : "C.D. Smith Construction, Inc.",
    "c.t. and s. metalworks" : "C.T. and S. Metalworks",
    "canam ponts canada inc" : "Canam Ponts Canada inc",
    "chc fabricating corp." : "cHc Fabricating Corp.",
    "chc manufacturing, inc." : "CHc Manufacturing, Inc.",
    "china mcc22 group corporation co., ltd" : "China MCC22 Group Corporation Co., Ltd",
    "cimolai-hy" : "Cimolai-HY",
    "cives steel co. mid-south" : "Cives Steel Co. Mid-South",
    "cives steel co. mid-west division" : "Cives Steel Co. Mid-West Division",
    "cives steel company - mid-atlantic division" : "Cives Steel Company - Mid-Atlantic Division",
    "cives steel company north-west division" : "Cives Steel Company North-West Division",
    "cives steel company south-west division" : "Cives Steel Company South-West Division",
    "con-fab engineering & welding" : "Con-Fab Engineering & Welding",
    "con-serv, inc." : "Con-Serv, Inc.",
    "cooec-fluor heavy industries co., ltd." : "COOEC-Fluor Heavy Industries Co., Ltd.",
    "cos-win, inc." : "Cos-Win, Inc.",
    "ct&c  fab l.l.c" : "CT&C  Fab L.L.C",
    "d.a. collins companies" : "D.A. Collins Companies",
    "d.l. george & sons manufacturing, inc.": "D.L. George & Sons Manufacturing, Inc.",
    "d.s. brown - athens" : "D.S. Brown - Athens",
    "d.s. duggins welding, inc." : "D.S. Duggins Welding, Inc.",
    "daidung ii high-tech mechanical corporation long an" : "DaiDung II High-Tech Mechanical Corporation Long An",
    "daidung metallic manufacture construction & trade corporation" : "DaiDung Metallic Manufacture Construction & Trade Corporation",
    "daidung nghi son mechanical joint stock company" : "DaiDung Nghi Son Mechanical Joint Stock Company",
    "daidung shipyard joint stock company" : "DaiDung Shipyard Joint Stock Company",
    "deangelis iron work, inc." : "DeAngelis Iron Work, Inc.",
    "delong's, inc." : "DeLong's, Inc.",
    "dhsteel products, llc" : "DHSteel Products, LLC",
    "di highway sign & structure corp." : "DI Highway Sign & Structure Corp.",
    "dis-tran steel, llc" : "DIS-TRAN Steel, LLC",
    "diversatech-metalfab, llc" : "Diversatech-Metalfab, LLC",
    "dixie crane services, inc dba dcs erectors" : "Dixie Crane Services, Inc dba DCS Erectors",
    "donahue mcnamara steel llc" : "Donahue McNamara Steel LLC",
    "drake-williams steel inc. - aurora plant" : "Drake-Williams Steel Inc. - Aurora Plant",
    "drake-williams steel, inc." : "Drake-Williams Steel, Inc.",
    "dubose national energy services, inc." : "DuBose National Energy Services, Inc.",
    "duo-gard industries" : "Duo-Gard Industries",
    "dura-bond steel corporation" : "Dura-Bond Steel Corporation",
    "e-z line pipe support co., llc" : "E-Z Line Pipe Support Co., LLC",
    "e.b.p. inc. dba epic steel company" : "E.B.P. Inc. dba EPIC Steel Company",
    "f.a. wilhelm construction co., inc." : "F.A. Wilhelm Construction Co., Inc.",
    "fab-weld steel, llc" : "Fab-Weld Steel, LLC",
    "fabarc steel supply" : "FabArc Steel Supply",
    "fineline steel fabrication" : "FineLine Steel Fabrication",
    "flexco construction, llc....dba flex-erect" : "FlexCo Construction, LLC....DBA Flex-Erect",
    "fresno fab-tech, inc." : "Fresno Fab-Tech, Inc.",
    "g. m. mccrossin, inc." : "G. M. McCrossin, Inc.",
    "g.a. west & co., inc." : "G.A. West & Co., Inc.",
    "g.t.e. metal fabricators, inc." : "G.T.E. Metal Fabricators, Inc.",
    "golden empire manufacturing, inc. dba gem buildings" : "Golden Empire Manufacturing, Inc. dba GEM Buildings",
    "greenberry industrial (gulf coast division)" : "Greenberry Industrial (Gulf Coast Division)",
    "gresham steel (a division of e.t. gresham)" : "Gresham Steel (a division of E.T. Gresham)",
    "h.a. fabricators" : "H.A. Fabricators",
    "harold o'shea builders" : "Harold O'Shea Builders",
    "henan d.r. construction group steel structure co.,ltd" : "Henan D.R. Construction Group Steel Structure Co.,Ltd",
    "industrial constructors/managers, inc." : "Industrial Constructors/Managers, Inc.",
    "j. a. mcmahon, inc." : "J. A. McMahon, Inc.",
    "j. c. macelroy company, inc." : "J. C. MacElroy Company, Inc.",
    "j.b. steel & precast, inc." : "J.B. Steel & Precast, Inc.",
    "j.b. ventures, inc. dba j.b. steel" : "J.B. Ventures, Inc. dba J.B. Steel",
    "j.b. ventures, inc." : "J.B. Ventures, Inc.",
    "j.d. eckman, inc." : "J.D. Eckman, Inc.",
    "j.h. botts, llc" : "J.H. Botts, LLC",
    "j.l. walter & associates, inc" : "J.L. Walter & Associates, Inc",
    "j.p. cullen & sons, inc." : "J.P. Cullen & Sons, Inc.",
    "j.p. donovan construction, inc. (jpd fabrication - rockledge, fl)" : "J.P. Donovan Construction, Inc. (JPD Fabrication - Rockledge, FL)",
    "j.r. hoe" : "J.R. Hoe",
    "jackrabbit manufacturing, llc" : "JackRabbit Manufacturing, LLC",
    "james a. mcbrady, inc.": "James A. McBrady, Inc.",
    "jd2 inc." : "JD2 Inc.",
    "jh findorff" : "JH Findorff",
    "jl walter & associates, inc" : "JL Walter & Associates, Inc",
    "kay-son steel fabricators ltd." : "KAY-SON Steel Fabricators Ltd.",
    "l.p.r. construction co." : "L.P.R. Construction Co.",
    "l.r. willson & sons, inc." : "L.R. Willson & Sons, Inc.",
    "l.s. steel, inc." : "L.S. Steel, Inc.",
    "lancaster burns construction, inc. (lb construction, inc.)" : "Lancaster Burns Construction, Inc. (LB Construction, Inc.)",
    "landscape structures inc./skyways division" : "Landscape Structures Inc./SkyWays Division",
    "lejeune steel - minneapolis" : "LeJeune Steel - Minneapolis",
    "lemar industries" : "LeMar Industries",
    "m.c.s. steel public company, ltd." : "M.C.S. Steel Public Company, Ltd.",
    "m.l. ruberton construction co., inc." : "M.L. Ruberton Construction Co., Inc.",
    "m.s. iron works inc.": "M.S. Iron Works Inc.",
    "macdougall steel erectors, inc." : "MacDougall Steel Erectors, Inc.",
    "march-westin" : "March-Westin",
    "mas building & bridge, inc." : "MAS Building & Bridge, Inc.",
    "mcalister welding & fabricating inc." : "McAlister Welding & Fabricating Inc.",
    "mcclean iron works" : "McClean Iron Works",
    "mccombs steel company, inc." : "McCombs Steel Company, Inc.",
    "mcdaniel steel erection" : "McDaniel Steel Erection",
    "mcfarlane mfg. company, inc. structural division" : "McFarlane Mfg. Company, Inc. Structural Division",
    "mcgregor industries, inc.": "McGregor Industries, Inc.",
    "mcpeak supply, llc": "McPeak Supply, LLC",
    "me&i holdings, inc" : "ME&I Holdings, Inc",
    "met-con, inc.": "Met-Con, Inc.",
    "metal-weld specialties, inc." : "Metal-Weld Specialties, Inc.",
    "metalstorm llc" : "MetalStorm LLC",
    "mi-de-con, inc." : "Mi-De-Con, Inc.",
    "mid-atlantic steel, llc." : "Mid-Atlantic Steel, LLC.",
    "mid-city steel, inc." : "Mid-City Steel, Inc.",
    "mid-ohio mechanical, inc." : "Mid-Ohio Mechanical, Inc.",
    "mid-park highway" : "Mid-Park Highway",
    "mid-state welding" : "Mid-State Welding",
    "mid-states material handling and fabrication" : "Mid-States Material Handling and Fabrication",
    "mid-states steel corp." : "Mid-States Steel Corp.",
    "modern modular engineering & construction (su zhou) co., ltd" : "Modern Modular Engineering & Construction (Su Zhou) Co., Ltd",
    "n.a. structures inc." : "N.A. Structures Inc.",
    'national steel fabrication co. "nsf"' : 'National Steel Fabrication Co. "NSF"',
    "o'brien steel erectors, inc." : "O'Brien Steel Erectors, Inc.",
    "o'rourke & sons, inc." : "O'Rourke & Sons, Inc.",
    "olsen-beal associates" : "Olsen-Beal Associates",
    "p.h. drew inc." : "P.H. Drew Inc.",
    "pennfab, inc." : "PennFab, Inc.",
    "preston fabrication id llc" : "Preston Fabrication ID LLC",
    "prometal sf&e" : "PROMETAL SF&E",
    "r.g. steel corp." : "R.G. Steel Corp.",
    "r.i. welding & fabricating co." : "R.I. Welding & Fabricating Co.",
    "r.t.i. fabrication, inc." : "R.T.I. Fabrication, Inc.",
    "rj watson llc" : "RJ Watson LLC",
    "s. a. halac iron works, inc." : "S. A. Halac Iron Works, Inc.",
    "s.e.k. construction, inc." : "S.E.K. Construction, Inc.",
    "s.i e&c viet nam company limited (f.k.a. posco e&c)" : "S.I E&C Viet Nam Company Limited (f.k.a. POSCO E&C)",
    "saskarc, inc. d.b.a inframod" : "Saskarc, Inc. d.b.a infraMOD",
    "schuff steel company--salt lake" : "Schuff Steel Company--Salt Lake",
    "shureline construction" : "ShureLine Construction",
    "shureline construction": "ShureLine Construction",
    "simpson strong-tie company inc." : "Simpson Strong-Tie Company Inc.",
    "simpson strong-tie company, inc. | stockton" : "Simpson Strong-Tie Company, Inc. | Stockton",
    "sinoma-tangshan heavy machinery co.,ltd.-tangshan port branch" : "Sinoma-Tangshan Heavy Machinery Co.,Ltd. - Tangshan Port Branch",
    "st. george steel llc." : "St. George Steel LLC.",
    "steel-crete inc" : "Steel-Crete Inc",
    "steel-plus, llc" : "Steel-Plus, LLC",
    "steelfab of dublin" : "SteelFab of Dublin",
    "steelfab of fayetteville" : "SteelFab of Fayetteville",
    "steelfab of sc" : "SteelFab of SC",
    "steelfab of virginia, inc." : "SteelFab of Virginia, Inc.",
    "steelfab texas, inc." : "SteelFab Texas, Inc.",
    "steelfab west, inc." : "SteelFab West, Inc.",
    "steelfab, inc. york" : "SteelFab, Inc. York",
    "steelfab, inc." : "SteelFab, Inc.",
    "steelfab, incorporated" : "STEELFAB, Incorporated",
    "steelgen, llc" : "SteelGen, LLC",
    "steelpro llc" : "SteelPro LLC",
    "stewart-amos steel, inc." : "Stewart-Amos Steel, Inc.",
    "stp&i public company limited" : "STP&I Public Company Limited",
    "structure sbl inc." : "Structure SBL Inc.",
    "sts steel, inc." : "STS Steel, Inc.",
    "sunsteel llc" : "SunSteel LLC",
    "synergi llc" : "SYNERGi LLC",
    "t-rex steel co., ltd." : "T-Rex Steel Co., Ltd.",
    "t.w.s. fabricators, inc.": "T.W.S. Fabricators, Inc.",
    "tc-iron works" : "TC-Iron Works",
    "tc-iron" : "TC-Iron",
    "tech-steel, inc." : "Tech-Steel, Inc.",
    "tei construction services, inc." : "TEi Construction Services, Inc.",
    "the l.c. whitford co., inc." : "The L.C. Whitford Co., Inc.",
    "toptiersteel" : "TopTier Steel",
    "tri-steel fabricators, inc." : "Tri-Steel Fabricators, Inc.",
    "tri-steel, inc." : "Tri-Steel, Inc.",
    "truenorth steel - billings" : "TrueNorth Steel - Billings",
    "truenorth steel - fargo" : "TrueNorth Steel - Fargo",
    "truenorth steel - lubbock" : "TrueNorth Steel - Lubbock",
    "truenorth steel - mandan" : "TrueNorth Steel - Mandan",
    "truenorth steel - rapid city" : "TrueNorth Steel - Rapid City",
    "truenorth steel - west fargo" : "TrueNorth Steel - West Fargo",
    "tubal-cain industries, inc." : "Tubal-Cain Industries, Inc.",
    "virginia-carolina steel, inc." : "Virginia-Carolina Steel, Inc.",
    "w-industries of texas llc" : "W-Industries of Texas LLC",
    "w.e.b. production & fabricating, inc." : "W.E.B. Production & Fabricating, Inc.",
    "w&w|afco steel -little rock port frazier location" : "W&W|AFCO Steel - Little Rock Port Frazier Location",
    "w&w|afco steel" : "W&W|AFCO Steel",
    "wells/mccoy steel service inc." : "Wells/ McCoy Steel Service Inc.",
    "wmk-billings" : "WMK-Billings",
    "wmk-kalispell" : "WMK-Kalispell",
    "zhongming heavy steel engineering (jiangsu nantong) co., ltd." : "Zhongming Heavy Steel Engineering (Jiangsu Nantong) Co., Ltd.",
    "zpmc-nantong zhenhua heavy equipment manufacturing co., ltd." : "ZPMC-Nantong Zhenhua Heavy Equipment Manufacturing Co., Ltd.",
}

def clean_phone(phone_val):
    """
    Formats phone numbers to standard XXX.XXX.XXXX, isolating 
    and cleanly appending extensions with a trailing ' x'.
    """
    if not phone_val or phone_val == "":
        return ""
    if pd.isna(phone_val) or str(phone_val).strip().lower() in ['nan', 'none', '']:
        return ""

# 🌟 NEW INTERNATIONAL SAFEGUARD:
    # If the number already contains a dot, assume it has been manually
    # verified or structured as an international exception. Return as-is.
    if "." in phone_val:
        return phone_val

    phone_str = str(phone_val).strip()
    
    # 1. ISOLATE THE EXTENSION FIRST
    # Searches for 'x', 'ext', or 'extension' followed by any digits
    ext_match = re.search(r'(?:x|ext|extension)\s*(\d+)', phone_str, re.IGNORECASE)
    extension_digits = ext_match.group(1) if ext_match else ""
    
    # 2. REMOVE THE EXTENSION TEXT FROM THE BASE STRING
    # Blasts away the extension part so its digits don't contaminate the base number
    if ext_match:
        phone_str = phone_str[:ext_match.start()]
    
    # 3. EXTRACT ONLY THE BASE DIGITS
    base_digits = "".join(filter(str.isdigit, phone_str))
    
    # Handle standard US country code prefix (e.g., +1 or 1)
    if len(base_digits) == 11 and base_digits.startswith('1'):
        base_digits = base_digits[1:]
        
    # 4. EVALUATE AND ASSEMBLE
    if len(base_digits) == 10:
        formatted_base = f"{base_digits[0:3]}.{base_digits[3:6]}.{base_digits[6:10]}"
        
        # Append the extension cleanly separated by a space and a lowercase x
        if extension_digits:
            return f"{formatted_base} x{extension_digits}"
        return formatted_base
        
    # If it's an international or non-standard digit length, return original as-is
    return str(phone_val).strip()

def fix_capitalization(text_val):
    """
    Advanced Tokenization Engine: Converts text to Title Case while dynamically
    enforcing rule matrices for parentheses, prepositions, ampersands, and acronyms.
    """
    if not text_val or text_val == "":
        return ""
    
    # --- PHASE 0: IMMEDIATE INTERCEPT ---
    raw_lookup = str(text_val).strip().lower()
    if raw_lookup in EXACT_COMPANY_OVERRIDES:
        return EXACT_COMPANY_OVERRIDES[raw_lookup]
    
    # --- PHASE 0.5: AMPERSAND SPACING PAD (NEW) ---
    # Safely forces a single space on both sides of any ampersand, 
    # breaking up squished text like "George&Sons" or "A&E" into "George & Sons"
    # EXCEPT if it's explicitly "A&E" (which is in your allowed acronyms)
    text_str = str(text_val).strip()
    if text_str.upper() != "A&E":
        text_str = re.sub(r'\s*&\s*', ' & ', text_str)
    
    # --- PHASE 1: DYNAMIC CONTEXTUAL TOKENIZATION ---
    words = str(text_val).strip().split()
    cleaned_words = []
    
    # Context Tracking Flags
    previous_word_was_ampersand = False

    for index, word in enumerate(words):
        # Strip trailing commas or periods just for checking acronym/preposition status
        clean_word_stripped = word.upper().replace('.', '').replace(',', '')
        lower_word_stripped = word.lower().replace('.', '').replace(',', '')
        
        # RULE 1: Word Inside Parentheses (e.g., "(FULTON)")
        # If it starts and ends with parens, preserve the original string value casing inside
        if word.startswith('(') and word.endswith(')'):
            cleaned_words.append(word)
            previous_word_was_ampersand = False
            continue

        # RULE 2: Allowed Acronym Engine (e.g., "DBA", "LLC")
        if clean_word_stripped in ALLOWED_ACRONYMS:
            cleaned_words.append(word.upper())
            previous_word_was_ampersand = False
            continue

        # RULE 3: Capitalization After an Ampersand (e.g., "& Sons")
        if previous_word_was_ampersand:
            cleaned_words.append(word.capitalize())
            previous_word_was_ampersand = (word == '&')
            continue

        # RULE 4: Lowercase Prepositions / Connectors (e.g., "de", "and", "of")
        # They stay lowercase UNLESS they are the very first word in the company name
        if lower_word_stripped in LOWERCASE_WORDS and index > 0:
            # Preserve punctuation if it was typed as "of," or "and."
            if word.endswith(',') or word.endswith('.'):
                cleaned_words.append(word.lower())
            else:
                cleaned_words.append(lower_word_stripped)
            previous_word_was_ampersand = (word == '&')
            continue

        # DEFAULT FALLBACK: Standard Native Title Casing
        cleaned_words.append(word.capitalize())
        
        # Set ampersand state for the NEXT word evaluation loop
        previous_word_was_ampersand = (word == '&')
            
    title_cased_text = " ".join(cleaned_words)
    
# --- PHASE 2: INTERNATIONAL INTERCEPT ENGINE (AMENDED) ---
    for lower_token, exact_casing in INTERNATIONAL_SUFFIX_MAP.items():
        # If the international suffix contains periods (like s.a. or b.v.), 
        # we enforce that the periods MUST be matched literally in the text
        escaped_token = re.escape(lower_token)
        
# CHANGED: Swapped the strict end-of-string anchor ($) for a flexible 
        # word/punctuation boundary. This catches "S.p.A." even if it's followed 
        # by notes in parentheses, like "(Polcenigo)".
        pattern = re.compile(rf'(?<!\w){escaped_token}(?!\w)', re.IGNORECASE)
        title_cased_text = pattern.sub(exact_casing, title_cased_text)
        
# --- PHASE 2.5: TWO-LETTER AMPERSAND REPAIR & COMPRESSION (UPDATED) ---
    # 1. First, make sure both letters are capitalized (handles "J & b" -> "J & B")
    title_cased_text = re.sub(r'\b([A-Z])\s*&\s*([a-z])\b', lambda m: f"{m.group(1)} & {m.group(2).upper()}", title_cased_text)
    
    # 2. Then, compress single-letter joins back together (handles "J & B" -> "J&B")
    # This matches a standalone capital letter, a space, an ampersand, a space, and another capital letter
    title_cased_text = re.sub(r'\b([A-Z])\s*&\s*([A-Z])\b', r'\1&\2', title_cased_text)
        
    return title_cased_text

def is_name_equivalent(name_a, name_b):
    """Checks if two names are equivalent or formal/informal variants (e.g., Bob vs Robert)."""
    clean_a = str(name_a).strip().lower()
    clean_b = str(name_b).strip().lower()
    
    if clean_a == clean_b:
        return True
        
    # Resolve nicknames using the dictionary mapping
    root_a = COMMON_NAMES.get(clean_a, clean_a)
    root_b = COMMON_NAMES.get(clean_b, clean_b)
    
    return root_a == root_b

def format_key_questions(row):
    """
    Compiles the 8 facility questionnaire answers into a clean markdown checklist,
    safely evaluating true Salesforce booleans, strings, or missing data points.
    """
    questions_mapping = {
        'Existing_equipment_moved_to_new_facility__c': 'Existing equipment moved to new facility',
        'Will_new_equipment_be_purchased__c': 'Will new equipment be purchased',
        'Will_old_equipment_be_removed__c': 'Will old equipment be removed',
        'Will_software_change__c': 'Will software change',
        'Will_QMS_or_documentation_change__c': 'Will QMS or documentation change',
        'Will_you_change_personnel__c': 'Will you change personnel',
        'Did_the_Cert_contact_change__c': 'Did the Cert conact change', 
        'Did_the_executive_manager_change__c': 'Did the executive manager change',
    }
    
    bullets = []
    
    for api_field, display_text in questions_mapping.items():
        val = row.get(api_field)
        
        # Safe Boolean & String Normalization Engine
        if val is True or str(val).strip().lower() in ['true', 'yes', '1']:
            status = "Yes"
        elif val is False or str(val).strip().lower() in ['false', 'no', '0'] or pd.isna(val) or val == "":
            status = "No"
        else:
            status = "No" # Default fallback safety
            
        bullets.append(f"• {display_text}: {status}")
        
    return "\n".join(bullets)

def is_valid_explanation(text):
    """
    Text Scrubbing Engine: Evaluates explanation text fields
    to filter out false positives and low-value administrative noise.
    """
    import pandas as pd
    if not text or pd.isna(text):
        return False
    
    clean_text = str(text).strip().lower()
    if len(clean_text) < 5:
        return False
        
    ignore_phrases = ["not applicable", "n/a", "not at this time", "none"]
    if clean_text in ignore_phrases:
        return False
        
    return True

def create_history_cache_row(case_id, case_number, account_id, contact_id, case_subject):
    """
    Standardizes the data dictionary structure for injecting new case logs
    back into the local pu_cases_1mhistory.csv tracking matrix.
    """
    from datetime import datetime
    current_timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.000+0000')
    
    return {
        'Id': case_id,
        'Case.Name': case_number,
        'ContactId': contact_id,
        'AccountId': account_id,
        'Status': 'Pending',
        'Subject': case_subject,
        'CreatedDate': current_timestamp,
        'LastModifiedDate': current_timestamp
    }

import re
import pandas as pd

def evaluate_contacts_for_single_account(account_id, df_staged_group, df_sf_contacts, contact_email_to_id, contact_email_to_name):
    """
    Analyzes staged contact records for a single Account ID.
    Categorizes updates into automated title backfills, straightforward human-review items, and unclear conflicts.
    """
    actions = {
        'automated_title_patches': [],  # Safe live updates (blank CRM title -> submitted title)
        'straightforward_reviews': [],  # Phone or name deviations that need a Y/N nod
        'unclear_exceptions': [],       # Multi-email collisions or unrecognized names
        'net_new_loader_rows': []       # Clean new additions to buffer for Data Loader CSV
    }
    
    unique_staged_contacts = {}
    roles_config = {
        'Cert': ('Cert_First_Name__c', 'Cert_Last_Name__c', 'Cert_Title__c', 'Cert_Email__c', 'Cert_Phone__c'),
        'Principal': ('Principal_First_Name__c', 'Principal_Last_Name__c', 'Principal_Title__c', 'Principal_Email__c', 'Principal_Phone__c'),
        'AP': ('AP_First_Name__c', 'AP_Last_Name__c', 'AP_Title__c', 'AP_Email__c', 'AP_Phone__c'),
        'Quality': ('Quality_First_Name__c', 'Quality_Last_Name__c', 'QC_Title__c', 'Quality_Email__c', 'Quality_Phone__c')
    }

    # 1. Consolidate submissions for this specific account scope
    for _, row in df_staged_group.iterrows():
        for role_label, fields in roles_config.items():
            f_first, f_last, f_title, f_email, f_phone = fields
            email = str(row.get(f_email, '')).strip().lower()
            
            if not email or email == "":
                continue
                
            first = str(row.get(f_first, '')).strip()
            last = str(row.get(f_last, '')).strip()
            title = str(row.get(f_title, '')).strip()
            phone = str(row.get(f_phone, '')).strip()
            
            if email not in unique_staged_contacts:
                unique_staged_contacts[email] = {
                    'First': first, 'Last': last, 'Phone': phone,
                    'Titles_Submitted': set([title]) if title else set()
                }
            else:
                if title:
                    unique_staged_contacts[email]['Titles_Submitted'].add(title)
                if not unique_staged_contacts[email]['Phone'] and phone:
                    unique_staged_contacts[email]['Phone'] = phone

    # 2. Deep verification comparison loops
    for email, staged in unique_staged_contacts.items():
        submitted_titles = list(staged['Titles_Submitted'])
        resolved_title = submitted_titles[0] if len(submitted_titles) == 1 else ""
        
        # Scenario A: True Net-New Contact Assignment
        if email not in df_sf_contacts.index:
            actions['net_new_loader_rows'].append({
                'AccountId': account_id, 'FirstName': staged['First'], 'LastName': staged['Last'],
                'Title': resolved_title, 'Email': email, 'Phone': staged['Phone']
            })
            continue

        # Scenario B: Email Exists - Run Profile Audit
        sf_matches = df_sf_contacts.loc[[email]]
        for _, sf_con in sf_matches.iterrows():
            sf_contact_id = sf_con.get('Id')
            discrepancies = []
            
            # Name auditing checks
            if staged['First'].lower() != str(sf_con.get('FirstName', '')).strip().lower():
                discrepancies.append(f"First Name ('{sf_con.get('FirstName')}' -> '{staged['First']}')")
            if staged['Last'].lower() != str(sf_con.get('LastName', '')).strip().lower():
                discrepancies.append(f"Last Name ('{sf_con.get('LastName')}' -> '{staged['Last']}')")

            # Title handling
            sf_title = str(sf_con.get('Title', '')).strip()
            if sf_title.lower() in ['nan', 'none', 'null']: sf_title = ""
            
            if sf_title == "" and len(submitted_titles) == 1:
                # Blank baseline title -> safe auto update patch package
                actions['automated_title_patches'].append({
                    'ContactId': sf_contact_id, 'Email': email, 'TargetTitle': resolved_title
                })
            elif len(submitted_titles) == 1 and resolved_title.lower() != sf_title.lower():
                discrepancies.append(f"Title Variation ('{sf_title}' -> '{resolved_title}')")
            elif len(submitted_titles) > 1:
                discrepancies.append(f"Conflicting Multiple Titles Submitted: {submitted_titles}")

            # Phone Auditing
            if staged['Phone'] != "" and "." not in staged['Phone']:
                # (Assumes your standard phone normalizer logic executes comparison)
                discrepancies.append(f"Phone variance detected against CRM Main line.")

            # Route findings based on clarity rules
            if discrepancies:
                actions['straightforward_reviews'].append({
                    'ContactId': sf_contact_id, 'Email': email, 'Name': f"{staged['First']} {staged['Last']}", 'Issues': discrepancies
                })
                
    return actions


def propose_account_role_swaps_for_single_account(account_id, df_staged_group, live_sf_account_row, contact_email_to_id, contact_email_to_name, df_sf_contacts):
    """
    Analyzes staged contact information to propose Account role seat modifications.
    Returns clear lists categorized by perfect matches, valid modifications, and structural conflicts.
    """
    analysis = {'perfect_matches': [], 'proposed_swaps': [], 'multiplicity_conflicts': [], 'unknown_emails': []}
    
    roles_schema_map = {
        'Certification Contact': ('Cert_Email__c', 'Cert_Certification_Contact__c'),
        'Principal Contact': ('Principal_Email__c', 'Cert_Principal_Contact__c'),
        'Accounting Contact': ('AP_Email__c', 'Cert_Accounting_Contact__c'),
        'Quality Contact': ('Quality_Email__c', 'Cert_Marketing_contact__c')
    }

    for role_label, (staging_email_field, sf_lookup_field) in roles_schema_map.items():
        submitted_emails = set()
        for _, row in df_staged_group.iterrows():
            em = str(row.get(staging_email_field, '')).strip().lower()
            if em: submitted_emails.add(em)
                
        if not submitted_emails:
            continue
            
        current_sf_contact_id = live_sf_account_row.get(sf_lookup_field)
        
        if len(submitted_emails) > 1:
            analysis['multiplicity_conflicts'].append({
                'Role': role_label, 'Emails': list(submitted_emails)
            })
        elif len(submitted_emails) == 1:
            submitted_email = list(submitted_emails)[0]
            
            if submitted_email not in contact_email_to_id:
                analysis['unknown_emails'].append({
                    'Role': role_label, 'Email': submitted_email
                })
                continue
                
            target_contact_id = contact_email_to_id[submitted_email]
            target_contact_name = contact_email_to_name[submitted_email]
            
            current_email = ""
            if current_sf_contact_id and current_sf_contact_id in df_sf_contacts.index:
                current_email = str(df_sf_contacts.loc[current_sf_contact_id].get('Email', '')).strip().lower()
                
            if submitted_email == current_email:
                analysis['perfect_matches'].append(f"{role_label}: {target_contact_name} is already seated correctly.")
            else:
                analysis['proposed_swaps'].append({
                    'Role': role_label, 'Field': sf_lookup_field, 'ContactId': target_contact_id, 'Name': target_contact_name, 'Email': submitted_email
                })
                
    return analysis

