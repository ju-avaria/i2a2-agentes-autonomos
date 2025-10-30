/* ======== YARA index ======== */
import "pe"
import "elf"
import "macho"

/* Bloqueia executáveis */
rule block_executable_formats {
  meta:
    description = "Bloqueia executáveis reais (PE/ELF/Mach-O) usando parsers dos módulos"
    severity    = "high"
  condition:
    pe.is_pe or elf.is_elf or macho.is_macho
}

rule xml_root_hint {
  meta:
    description = "Arquivo parece ser XML (hint informativo)"
    severity    = "info"
  strings:
    $xml_decl = /^(\xEF\xBB\xBF)?\s*<\?xml/i ascii
    $nfe_tag  = /<NFe(\s|>)/ ascii
  condition:
    any of them
}

/* indica DTD ativa*/
rule xml_has_doctype_or_entity {
  meta:
    description = "Presença de DOCTYPE/ENTITY (pode habilitar XXE/expansão de entidades)"
    severity    = "medium"
  strings:
    $dtd1 = /<!DOCTYPE/i ascii
    $ent1 = /<!ENTITY/i ascii
  condition:
    any of them
}

rule xml_xxe_external_entities {
  meta:
    description = "Possível XXE: ENTITY externa com SYSTEM/PUBLIC"
    severity    = "high"
  strings:
    $sys  = /<!ENTITY\s+[^>]+?\s+SYSTEM\s+["'][a-z]+:\/\//i ascii
    $pub  = /<!ENTITY\s+[^>]+?\s+PUBLIC\s+["'][^"']+["']\s+["'][a-z]+:\/\//i ascii
    $parm = /%\s*[a-z0-9_:-]+\s*;/i ascii                   // entidades paramétricas
  condition:
    $parm or $sys or $pub
}


rule xml_external_protocols {
  meta:
    description = "Referências externas em atributos (file://, http(s)://, ftp://, jar:, data:)"
    severity    = "medium"
  strings:
    $p1 = /(href|src|xlink:href)\s*=\s*["'](file|https?|ftp|gopher|jar):\/\//i ascii
    $p2 = /(href|src|xlink:href)\s*=\s*["']data:/i ascii
  condition:
    any of them
}


rule xml_xinclude {
  meta:
    description = "Presença de XInclude"
    severity    = "info"
  strings:
    $xi = /<xi:include\b/i ascii
  condition:
    $xi
}


rule xml_large_base64 {
  meta:
    description = "Chunk grande base64 no XML (512+ chars)"
    severity    = "info"
  strings:
    $b64 = /[A-Za-z0-9+\/=]{512,}/ ascii
  condition:
    $b64
}

/* Script dentro do XML  */
rule xml_script_tag {
  meta:
    description = "Tag <script> dentro do XML"
    severity    = "medium"
  strings:
    $s1 = /<script\b/i ascii
  condition:
    $s1
}


rule xml_stylesheet_external {
  meta:
    description = "xml-stylesheet com href externo"
    severity    = "info"
  strings:
    $pi = /\?xml-stylesheet[^>]+href=["'](file|https?|ftp|gopher|jar):\/\//i ascii
  condition:
    $pi
}
