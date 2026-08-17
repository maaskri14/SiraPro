# منشئ السيرة الاحترافية

تطبيق ويب عربي مبني ببايثون لإنشاء سيرة ذاتية واضحة ومتوافقة مع أنظمة ATS.

## التشغيل

```bash
pip install -r requirements.txt
python3 server.py
```

ثم افتح `http://localhost:8000`.

## Mode commercial et licences

L'application démarre en mode évaluation : aperçu et score ATS disponibles,
mais impression et exports désactivés. La protection est appliquée dans
l'interface **et** sur le serveur.

Avant une mise en production, définissez un secret privé long :

```powershell
$env:CV_LICENSE_SECRET="remplacez-par-un-secret-aleatoire-tres-long"
python server.py
```

Pour créer une licence de test ou une licence vendue manuellement :

```powershell
python license_admin.py client@example.com --plan monthly
python license_admin.py client@example.com --plan annual
```

Communiquez la clé affichée au client. Une licence accepte deux appareils par
défaut et le jeton local est renouvelable pendant sept jours.

### Liens de paiement

Tarifs affichés : **500 DA par mois** ou **5 000 DA par an**.

Les boutons mensuel et annuel utilisent Chargily par défaut. Configurez les
liens réels dans les variables d'environnement :

```powershell
$env:CV_CHARGILY_MONTHLY_URL="https://votre-lien-mensuel"
$env:CV_CHARGILY_ANNUAL_URL="https://votre-lien-annuel"
```

Tant que ces variables ne sont pas configurées, le paiement reste en mode test.
L'activation automatique après paiement nécessite ensuite de relier les
webhooks signés Chargily/Paddle à la création de licence.

## المزايا

- نموذج عربي موجّه مع معاينة فورية.
- تقييم ATS مع تنبيهات عملية.
- ترتيب الخبرات زمنيًا من الأحدث.
- حفظ تلقائي محلي في المتصفح.
- تصدير PDF وDOCX وHTML وTXT وJSON.
- دعم عربي صحيح في PDF مع اتجاه RTL، وترميز UTF-8 BOM لملفات HTML وTXT وJSON.
- يعمل على Windows دون الحاجة إلى تثبيت GTK أو Pango.
- واجهة بثلاث لغات: العربية والإنجليزية والفرنسية، مع تبديل اتجاه الصفحة تلقائيًا.
- شريط تصدير واضح وثابت قرب أسفل الشاشة على الهاتف.
- قالب بعمود واحد، دون جداول أو أيقونات داخل محتوى السيرة.
- Mode d'évaluation avec filigrane et exports verrouillés côté serveur.
- Activation par licence mensuelle ou annuelle, limitée à deux appareils.
- Modèle fictif « Nadia Benali » prérempli avec un score ATS de 100 %, disponible en français, anglais et arabe depuis le bouton « Exemple ATS ».

> ملاحظة: نتيجة ATS إرشادية، لأن كل شركة قد تستخدم نظامًا وقواعد فرز مختلفة.
