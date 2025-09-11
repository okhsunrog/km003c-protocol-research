#!/bin/bash
cp for_manual_splitting.jsonl for_manual_splitting.jsonl.bak
echo 'Original file backed up to for_manual_splitting.jsonl.bak'
sed -i '/"frame_number": 1/i \
# Transaction 1\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 1/\"transaction_id\": 1, \"frame_number\": 1/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 2/\"transaction_id\": 1, \"frame_number\": 2/' for_manual_splitting.jsonl
sed -i '/"frame_number": 3/i \
# Transaction 2\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 3/\"transaction_id\": 2, \"frame_number\": 3/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 4/\"transaction_id\": 2, \"frame_number\": 4/' for_manual_splitting.jsonl
sed -i '/"frame_number": 5/i \
# Transaction 3\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 5/\"transaction_id\": 3, \"frame_number\": 5/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 6/\"transaction_id\": 3, \"frame_number\": 6/' for_manual_splitting.jsonl
sed -i '/"frame_number": 291/i \
# Transaction 4\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 291/\"transaction_id\": 4, \"frame_number\": 291/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 292/\"transaction_id\": 4, \"frame_number\": 292/' for_manual_splitting.jsonl
sed -i '/"frame_number": 293/i \
# Transaction 5\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 293/\"transaction_id\": 5, \"frame_number\": 293/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 294/\"transaction_id\": 5, \"frame_number\": 294/' for_manual_splitting.jsonl
sed -i '/"frame_number": 295/i \
# Transaction 6\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 295/\"transaction_id\": 6, \"frame_number\": 295/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 296/\"transaction_id\": 6, \"frame_number\": 296/' for_manual_splitting.jsonl
sed -i '/"frame_number": 300/i \
# Transaction 7\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 300/\"transaction_id\": 7, \"frame_number\": 300/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 301/\"transaction_id\": 7, \"frame_number\": 301/' for_manual_splitting.jsonl
sed -i '/"frame_number": 302/i \
# Transaction 8\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 302/\"transaction_id\": 8, \"frame_number\": 302/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 303/\"transaction_id\": 8, \"frame_number\": 303/' for_manual_splitting.jsonl
sed -i '/"frame_number": 304/i \
# Transaction 9\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 304/\"transaction_id\": 9, \"frame_number\": 304/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 305/\"transaction_id\": 9, \"frame_number\": 305/' for_manual_splitting.jsonl
sed -i '/"frame_number": 306/i \
# Transaction 10\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 306/\"transaction_id\": 10, \"frame_number\": 306/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 307/\"transaction_id\": 10, \"frame_number\": 307/' for_manual_splitting.jsonl
sed -i '/"frame_number": 309/i \
# Transaction 11\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 309/\"transaction_id\": 11, \"frame_number\": 309/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 310/\"transaction_id\": 11, \"frame_number\": 310/' for_manual_splitting.jsonl
sed -i '/"frame_number": 311/i \
# Transaction 12\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 311/\"transaction_id\": 12, \"frame_number\": 311/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 312/\"transaction_id\": 12, \"frame_number\": 312/' for_manual_splitting.jsonl
sed -i '/"frame_number": 313/i \
# Transaction 13\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 313/\"transaction_id\": 13, \"frame_number\": 313/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 314/\"transaction_id\": 13, \"frame_number\": 314/' for_manual_splitting.jsonl
sed -i '/"frame_number": 326/i \
# Transaction 14\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 326/\"transaction_id\": 14, \"frame_number\": 326/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 327/\"transaction_id\": 14, \"frame_number\": 327/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 328/\"transaction_id\": 14, \"frame_number\": 328/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 329/\"transaction_id\": 14, \"frame_number\": 329/' for_manual_splitting.jsonl
sed -i '/"frame_number": 332/i \
# Transaction 15\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 332/\"transaction_id\": 15, \"frame_number\": 332/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 333/\"transaction_id\": 15, \"frame_number\": 333/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 334/\"transaction_id\": 15, \"frame_number\": 334/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 335/\"transaction_id\": 15, \"frame_number\": 335/' for_manual_splitting.jsonl
sed -i '/"frame_number": 338/i \
# Transaction 16\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 338/\"transaction_id\": 16, \"frame_number\": 338/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 339/\"transaction_id\": 16, \"frame_number\": 339/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 340/\"transaction_id\": 16, \"frame_number\": 340/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 341/\"transaction_id\": 16, \"frame_number\": 341/' for_manual_splitting.jsonl
sed -i '/"frame_number": 344/i \
# Transaction 17\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 344/\"transaction_id\": 17, \"frame_number\": 344/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 345/\"transaction_id\": 17, \"frame_number\": 345/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 346/\"transaction_id\": 17, \"frame_number\": 346/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 347/\"transaction_id\": 17, \"frame_number\": 347/' for_manual_splitting.jsonl
sed -i '/"frame_number": 348/i \
# Transaction 18\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 348/\"transaction_id\": 18, \"frame_number\": 348/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 349/\"transaction_id\": 18, \"frame_number\": 349/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 350/\"transaction_id\": 18, \"frame_number\": 350/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 351/\"transaction_id\": 18, \"frame_number\": 351/' for_manual_splitting.jsonl
sed -i '/"frame_number": 352/i \
# Transaction 19\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 352/\"transaction_id\": 19, \"frame_number\": 352/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 353/\"transaction_id\": 19, \"frame_number\": 353/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 354/\"transaction_id\": 19, \"frame_number\": 354/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 355/\"transaction_id\": 19, \"frame_number\": 355/' for_manual_splitting.jsonl
sed -i '/"frame_number": 356/i \
# Transaction 20\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 356/\"transaction_id\": 20, \"frame_number\": 356/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 357/\"transaction_id\": 20, \"frame_number\": 357/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 358/\"transaction_id\": 20, \"frame_number\": 358/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 359/\"transaction_id\": 20, \"frame_number\": 359/' for_manual_splitting.jsonl
sed -i '/"frame_number": 360/i \
# Transaction 21\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 360/\"transaction_id\": 21, \"frame_number\": 360/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 361/\"transaction_id\": 21, \"frame_number\": 361/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 362/\"transaction_id\": 21, \"frame_number\": 362/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 363/\"transaction_id\": 21, \"frame_number\": 363/' for_manual_splitting.jsonl
sed -i '/"frame_number": 412/i \
# Transaction 22\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 412/\"transaction_id\": 22, \"frame_number\": 412/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 413/\"transaction_id\": 22, \"frame_number\": 413/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 414/\"transaction_id\": 22, \"frame_number\": 414/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 415/\"transaction_id\": 22, \"frame_number\": 415/' for_manual_splitting.jsonl
sed -i '/"frame_number": 468/i \
# Transaction 23\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 468/\"transaction_id\": 23, \"frame_number\": 468/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 469/\"transaction_id\": 23, \"frame_number\": 469/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 470/\"transaction_id\": 23, \"frame_number\": 470/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 471/\"transaction_id\": 23, \"frame_number\": 471/' for_manual_splitting.jsonl
sed -i '/"frame_number": 522/i \
# Transaction 24\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 522/\"transaction_id\": 24, \"frame_number\": 522/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 523/\"transaction_id\": 24, \"frame_number\": 523/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 524/\"transaction_id\": 24, \"frame_number\": 524/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 525/\"transaction_id\": 24, \"frame_number\": 525/' for_manual_splitting.jsonl
sed -i '/"frame_number": 574/i \
# Transaction 25\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 574/\"transaction_id\": 25, \"frame_number\": 574/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 575/\"transaction_id\": 25, \"frame_number\": 575/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 576/\"transaction_id\": 25, \"frame_number\": 576/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 577/\"transaction_id\": 25, \"frame_number\": 577/' for_manual_splitting.jsonl
sed -i '/"frame_number": 622/i \
# Transaction 26\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 622/\"transaction_id\": 26, \"frame_number\": 622/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 623/\"transaction_id\": 26, \"frame_number\": 623/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 624/\"transaction_id\": 26, \"frame_number\": 624/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 627/\"transaction_id\": 26, \"frame_number\": 627/' for_manual_splitting.jsonl
sed -i '/"frame_number": 664/i \
# Transaction 27\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 664/\"transaction_id\": 27, \"frame_number\": 664/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 665/\"transaction_id\": 27, \"frame_number\": 665/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 666/\"transaction_id\": 27, \"frame_number\": 666/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 669/\"transaction_id\": 27, \"frame_number\": 669/' for_manual_splitting.jsonl
sed -i '/"frame_number": 694/i \
# Transaction 28\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 694/\"transaction_id\": 28, \"frame_number\": 694/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 695/\"transaction_id\": 28, \"frame_number\": 695/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 696/\"transaction_id\": 28, \"frame_number\": 696/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 697/\"transaction_id\": 28, \"frame_number\": 697/' for_manual_splitting.jsonl
sed -i '/"frame_number": 722/i \
# Transaction 29\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 722/\"transaction_id\": 29, \"frame_number\": 722/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 723/\"transaction_id\": 29, \"frame_number\": 723/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 724/\"transaction_id\": 29, \"frame_number\": 724/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 725/\"transaction_id\": 29, \"frame_number\": 725/' for_manual_splitting.jsonl
sed -i '/"frame_number": 746/i \
# Transaction 30\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 746/\"transaction_id\": 30, \"frame_number\": 746/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 747/\"transaction_id\": 30, \"frame_number\": 747/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 748/\"transaction_id\": 30, \"frame_number\": 748/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 749/\"transaction_id\": 30, \"frame_number\": 749/' for_manual_splitting.jsonl
sed -i '/"frame_number": 750/i \
# Transaction 31\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 750/\"transaction_id\": 31, \"frame_number\": 750/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 751/\"transaction_id\": 31, \"frame_number\": 751/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 752/\"transaction_id\": 31, \"frame_number\": 752/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 753/\"transaction_id\": 31, \"frame_number\": 753/' for_manual_splitting.jsonl
sed -i '/"frame_number": 764/i \
# Transaction 32\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 764/\"transaction_id\": 32, \"frame_number\": 764/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 765/\"transaction_id\": 32, \"frame_number\": 765/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 766/\"transaction_id\": 32, \"frame_number\": 766/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 767/\"transaction_id\": 32, \"frame_number\": 767/' for_manual_splitting.jsonl
sed -i '/"frame_number": 774/i \
# Transaction 33\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 774/\"transaction_id\": 33, \"frame_number\": 774/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 775/\"transaction_id\": 33, \"frame_number\": 775/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 776/\"transaction_id\": 33, \"frame_number\": 776/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 777/\"transaction_id\": 33, \"frame_number\": 777/' for_manual_splitting.jsonl
sed -i '/"frame_number": 778/i \
# Transaction 34\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 778/\"transaction_id\": 34, \"frame_number\": 778/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 779/\"transaction_id\": 34, \"frame_number\": 779/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 780/\"transaction_id\": 34, \"frame_number\": 780/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 781/\"transaction_id\": 34, \"frame_number\": 781/' for_manual_splitting.jsonl
sed -i '/"frame_number": 784/i \
# Transaction 35\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 784/\"transaction_id\": 35, \"frame_number\": 784/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 785/\"transaction_id\": 35, \"frame_number\": 785/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 786/\"transaction_id\": 35, \"frame_number\": 786/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 787/\"transaction_id\": 35, \"frame_number\": 787/' for_manual_splitting.jsonl
sed -i '/"frame_number": 788/i \
# Transaction 36\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 788/\"transaction_id\": 36, \"frame_number\": 788/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 789/\"transaction_id\": 36, \"frame_number\": 789/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 790/\"transaction_id\": 36, \"frame_number\": 790/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 791/\"transaction_id\": 36, \"frame_number\": 791/' for_manual_splitting.jsonl
sed -i '/"frame_number": 792/i \
# Transaction 37\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 792/\"transaction_id\": 37, \"frame_number\": 792/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 793/\"transaction_id\": 37, \"frame_number\": 793/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 794/\"transaction_id\": 37, \"frame_number\": 794/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 795/\"transaction_id\": 37, \"frame_number\": 795/' for_manual_splitting.jsonl
sed -i '/"frame_number": 796/i \
# Transaction 38\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 796/\"transaction_id\": 38, \"frame_number\": 796/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 797/\"transaction_id\": 38, \"frame_number\": 797/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 798/\"transaction_id\": 38, \"frame_number\": 798/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 799/\"transaction_id\": 38, \"frame_number\": 799/' for_manual_splitting.jsonl
sed -i '/"frame_number": 802/i \
# Transaction 39\n' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 802/\"transaction_id\": 39, \"frame_number\": 802/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 803/\"transaction_id\": 39, \"frame_number\": 803/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 804/\"transaction_id\": 39, \"frame_number\": 804/' for_manual_splitting.jsonl
sed -i 's/\"transaction_id\": 1, \"frame_number\": 805/\"transaction_id\": 39, \"frame_number\": 805/' for_manual_splitting.jsonl
