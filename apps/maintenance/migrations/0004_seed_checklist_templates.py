from django.db import migrations

# Source: NOM MACHINES ET PROGRAMME MAINTENANCE.pdf, page 2, "Maintenance
# préventive hebdomadaire" — transcribed row-for-row. Do not paraphrase these
# strings; plan.md §12 requires the checklist to preserve the PDF's
# structure/terminology exactly.
TEMPLATES = [
    {
        "key": "ISBM_88_110",
        "name": "ISBM 88/110",
        "sections": [
            ("Système hydraulique", [
                "Vérifier le niveau et la propreté de l'huile hydraulique",
                "Contrôler les flexibles et raccords",
                "Vérifier la température de l'huile",
            ]),
            ("Système de chauffage extrusion vis", [
                "Contrôler l'état des colliers chauffants et thermocouples",
                "Vérifier l'étalonnage des zones de température",
                "Inspecter les colliers de chauffage",
            ]),
            ("Moules et unités de soufflage", [
                "Nettoyer les cavités du moule",
                "Vérifier l'étanchéité des joints et canaux de refroidissement",
                "Contrôler les buses de soufflage",
                "Inspecter les tiges d'étirage",
            ]),
            ("Circuit pneumatique", [
                "Purger les condensats des filtres à air comprimé",
                "Vérifier la pression de soufflage haute et basse pression",
                "Contrôler les électrovannes",
                "Vérifier les raccords et les flexibles",
            ]),
            ("Système de refroidissement", [
                "Vérifier le débit et la température de l'eau glacée",
                "Vérifier les circuits de refroidissement du moule",
                "Contrôler l'absence de tartre dans les circuits",
            ]),
            ("Éléments mécaniques", [
                "Graisser les colonnes, glissières et systèmes de guidage",
                "Vérifier le serrage des vis et fixations",
            ]),
        ],
    },
    {
        "key": "INJECTION_1580",
        "name": "Injection 1580",
        "sections": [
            ("Système hydraulique", [
                "Vérifier le niveau d'huile hydraulique et son aspect",
                "Contrôler les flexibles, raccords et vérins pour fuites",
                "Vérifier la pression de fonctionnement d'injection maintenue",
            ]),
            ("Unité de plastification (vis et fourreau)", [
                "Vérifier les températures des zones de chauffe",
                "Inspecter les colliers chauffants et thermocouples",
                "Contrôler de la buse d'injection et alignement avec le moule",
                "Vérifier l'absence de résidus de matière carbonisée",
            ]),
            ("Moule", [
                "Nettoyer canaux de refroidissement",
                "Vérifier l'étanchéité des joints et circuits d'eau",
                "Contrôler des noyaux et cavités",
                "Vérifier l'alignement partie fixe/mobile",
                "Contrôler les éjecteurs",
            ]),
            ("Système de refroidissement", [
                "Vérifier débit et température de l'eau glacée",
                "Nettoyer les circuits refroidissement moule",
            ]),
            ("Colonnes et système de fermeture", [
                "Graisser les colonnes de guidage",
                "Vérifier l'usure des bagues et douilles",
                "Contrôler le parallélisme des plateaux",
            ]),
        ],
    },
    {
        "key": "COMPRESSOR",
        "name": "Compresseur",
        "sections": [
            ("Compresseur", [
                "Vérifier et nettoyer/remplacer le filtre à air d'admission",
                "Contrôler l'état du filtre à huile",
                "Vérifier le filtre séparateur air/huile",
                "Vérifier le niveau d'huile",
                "Purger manuellement le réservoir/ballon d'air",
                "Nettoyer les ailettes du radiateur",
                "Contrôler la pression de consigne et mesure",
                "Contrôler du cycle de régénération du sécheur",
            ]),
        ],
    },
]


def seed(apps, schema_editor):
    ChecklistTemplate = apps.get_model("maintenance", "ChecklistTemplate")
    ChecklistSection = apps.get_model("maintenance", "ChecklistSection")
    ChecklistItem = apps.get_model("maintenance", "ChecklistItem")

    for tpl in TEMPLATES:
        template, _ = ChecklistTemplate.objects.get_or_create(key=tpl["key"], defaults={"name": tpl["name"]})
        for section_order, (section_name, items) in enumerate(tpl["sections"]):
            section, _ = ChecklistSection.objects.get_or_create(
                template=template, name=section_name, defaults={"order": section_order},
            )
            for item_order, text in enumerate(items):
                ChecklistItem.objects.get_or_create(section=section, text=text, defaults={"order": item_order})


def unseed(apps, schema_editor):
    ChecklistTemplate = apps.get_model("maintenance", "ChecklistTemplate")
    ChecklistTemplate.objects.filter(key__in=[t["key"] for t in TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0003_checklistsection_checklisttemplate_checklistitem_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
