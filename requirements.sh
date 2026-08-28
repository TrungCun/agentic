# install với dependence
pip install -r requirements.in -c constraints.txt

# tạo requirements final
pip freeze > requirements.txt
pip check


# thêm dòng vào requirements.in
echo "sentence-transformers>=3.0" >> requirements.in
pip install -r requirements.in -c constraints.txt --upgrade-strategy only-if-needed

# khi conflict
pip install -r requirements.in -c constraints.txt --dry-run
# => check kỹ ResolutionImpossible

# fix conflict
pip install -r requirements.in -c constraints.txt   # cài phần chạy được trước
pip install <các gói cần cài> --no-deps                        # ép cài gói
pip check                                            # xem thiếu dependency nào
pip install <các gói pip check báo thiếu> -c constraints.txt
